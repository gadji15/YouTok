from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog


@dataclass(frozen=True)
class SubtitlePlacement:
    alignment: int
    x: int
    y: int

    # Diagnostics / metrics (best-effort)
    # - face_overlap_ratio: p95 overlap of subtitle box with detected face bbox area.
    # - ui_overlap_ratio: p95 overlap of subtitle box with the "bottom UI" safe zone.
    face_overlap_ratio: float = 0.0
    ui_overlap_ratio: float = 0.0

    # UI heuristic score (edge density proxy). Kept for debugging.
    ui_score: float = 0.0


def _edge_density(gray, *, x0: int, y0: int, x1: int, y1: int) -> float:
    import cv2

    roi = gray[y0:y1, x0:x1]
    if roi.size == 0:
        return 0.0

    edges = cv2.Canny(roi, 80, 200)
    return float(edges.mean() / 255.0)


def _extract_frames(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    work_dir: Path,
    sample_fps: int = 1,
    scale_w: int = 540,
) -> list[Path]:
    import shutil
    import subprocess

    frames_dir = work_dir / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    duration = max(0.0, end_seconds - start_seconds)
    if duration <= 0.1:
        return []

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(start_seconds),
                "-i",
                str(video_path),
                "-t",
                str(duration),
                "-vf",
                f"fps={sample_fps},scale={scale_w}:-1",
                str(frames_dir / "frame_%04d.jpg"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return sorted(frames_dir.glob("frame_*.jpg"))
    except Exception:
        return []


def _detect_faces_and_mouth_ymin_rel(
    frame_paths: list[Path],
) -> tuple[list[tuple[float, float, float, float]], float | None]:
    """Return face bbox(es) (xmin,ymin,xmax,ymax) in relative coords + mouth ymin.

    This is used only to compute candidate positions (above mouth).
    Overlap metrics are computed separately across sampled frames.
    """

    try:
        import cv2
        import mediapipe as mp
    except Exception:
        return [], None

    if not getattr(mp, "solutions", None) or not getattr(mp.solutions, "face_mesh", None):
        return [], None

    face_bboxes: list[tuple[float, float, float, float]] = []
    mouth_ymins: list[float] = []

    try:
        mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            refine_landmarks=True,
            max_num_faces=1,
            min_detection_confidence=0.5,
        )
    except Exception:
        return [], None

    mouth_idxs = {
        61,
        146,
        91,
        181,
        84,
        17,
        314,
        405,
        321,
        375,
        291,
        78,
        191,
        80,
        81,
        82,
        13,
        312,
        311,
        310,
        415,
        308,
    }

    try:
        for p in frame_paths:
            img = cv2.imread(str(p))
            if img is None:
                continue
            h, w = img.shape[:2]
            if h <= 0 or w <= 0:
                continue

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = mesh.process(rgb)
            if not res.multi_face_landmarks:
                continue

            lm = res.multi_face_landmarks[0].landmark

            xs = [float(pt.x) for pt in lm]
            ys = [float(pt.y) for pt in lm]

            xmin = max(0.0, min(xs))
            xmax = min(1.0, max(xs))
            ymin = max(0.0, min(ys))
            ymax = min(1.0, max(ys))
            face_bboxes.append((xmin, ymin, xmax, ymax))

            m_ys = [float(lm[i].y) for i in mouth_idxs if i < len(lm)]
            if m_ys:
                mouth_ymins.append(max(0.0, min(m_ys)))

    finally:
        mesh.close()

    mouth_ymin = (sum(mouth_ymins) / len(mouth_ymins)) if mouth_ymins else None
    return face_bboxes, mouth_ymin


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    xs = sorted(float(v) for v in values)
    # nearest-rank p95
    idx = int(round(0.95 * (len(xs) - 1)))
    idx = max(0, min(len(xs) - 1, idx))
    return float(xs[idx])


def _rect_inter_area(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    return ix * iy


def _rect_area(r: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = r
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _subtitle_box_rel(
    *,
    placement: SubtitlePlacement,
    play_res_x: int,
    play_res_y: int,
    box_h_px: int,
) -> tuple[float, float, float, float]:
    """Approximate subtitle bbox in relative coords.

    We assume subtitles span most of the width, with safe side margins.
    """

    sub_x0 = 0.08
    sub_x1 = 0.92

    if placement.alignment == 8:
        y0 = placement.y
        y1 = placement.y + box_h_px
    else:
        y0 = placement.y - box_h_px
        y1 = placement.y

    return (
        sub_x0,
        max(0.0, float(y0) / float(play_res_y)),
        sub_x1,
        min(1.0, float(y1) / float(play_res_y)),
    )


def _detect_face_bbox_rel_per_frame(frame_paths: list[Path]) -> list[tuple[float, float, float, float] | None]:
    """Return a single face bbox per frame (relative coords) or None."""

    try:
        import cv2
        import mediapipe as mp
    except Exception:
        return [None for _ in frame_paths]

    if not getattr(mp, "solutions", None) or not getattr(mp.solutions, "face_detection", None):
        return [None for _ in frame_paths]

    try:
        det = mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)
    except Exception:
        return [None for _ in frame_paths]

    out: list[tuple[float, float, float, float] | None] = []

    try:
        for p in frame_paths:
            img = cv2.imread(str(p))
            if img is None:
                out.append(None)
                continue

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = det.process(rgb)
            if not res.detections:
                out.append(None)
                continue

            bbox = res.detections[0].location_data.relative_bounding_box
            x0 = max(0.0, float(bbox.xmin))
            y0 = max(0.0, float(bbox.ymin))
            x1 = min(1.0, float(bbox.xmin + bbox.width))
            y1 = min(1.0, float(bbox.ymin + bbox.height))
            if x1 <= x0 or y1 <= y0:
                out.append(None)
                continue

            out.append((x0, y0, x1, y1))

        return out
    finally:
        try:
            det.close()
        except Exception:
            pass


def _compute_overlap_metrics(
    *,
    frame_paths: list[Path],
    placement: SubtitlePlacement,
    play_res_x: int,
    play_res_y: int,
    box_h_px: int,
    ui_safe_ymin: float = 0.78,
) -> tuple[float, float]:
    """Return (face_overlap_p95, ui_overlap_p95)."""

    sub = _subtitle_box_rel(placement=placement, play_res_x=play_res_x, play_res_y=play_res_y, box_h_px=box_h_px)

    # Bottom UI safe zone (configurable): assume UI occupies the region y>=ui_safe_ymin.
    ui = (0.0, float(ui_safe_ymin), 1.0, 1.0)

    face_overlaps: list[float] = []
    ui_overlaps: list[float] = []

    sub_area = max(1e-6, _rect_area(sub))

    face_boxes = _detect_face_bbox_rel_per_frame(frame_paths)

    for fb in face_boxes:
        if fb is not None:
            face_area = max(1e-6, _rect_area(fb))
            face_overlaps.append(_rect_inter_area(sub, fb) / face_area)

        ui_overlaps.append(_rect_inter_area(sub, ui) / sub_area)

    return _p95(face_overlaps), _p95(ui_overlaps)


def measure_overlap_p95_for_video(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    placement: SubtitlePlacement,
    play_res_x: int,
    play_res_y: int,
    work_dir: Path,
    logger: structlog.BoundLogger,
    sample_fps: int = 1,
    ui_safe_ymin: float = 0.78,
) -> tuple[float, float]:
    """Measure overlap p95 on a rendered clip.

    This extracts frames from the provided video and runs face detection per frame.
    It is best-effort (returns zeros when CV deps are missing).

    Returns: (face_overlap_p95, ui_overlap_p95)
    """

    frames = _extract_frames(
        video_path=video_path,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        work_dir=work_dir,
        sample_fps=sample_fps,
        scale_w=540,
    )

    if not frames:
        return 0.0, 0.0

    try:
        box_h = int(play_res_y * 0.14)
        return _compute_overlap_metrics(
            frame_paths=frames,
            placement=placement,
            play_res_x=play_res_x,
            play_res_y=play_res_y,
            box_h_px=box_h,
            ui_safe_ymin=ui_safe_ymin,
        )
    except Exception:
        logger.exception("subtitles.overlap_measure_failed")
        return 0.0, 0.0


def choose_subtitle_placement(
    *,
    source_video: Path,
    clip_start_seconds: float,
    clip_end_seconds: float,
    play_res_x: int,
    play_res_y: int,
    work_dir: Path,
    logger: structlog.BoundLogger,
    ui_safe_ymin: float = 0.78,
) -> SubtitlePlacement:
    """Pick a safe subtitle placement.

    Best-effort:
    - If CV deps are missing or no faces detected => bottom-center with safe margin.
    - Otherwise pick among bottom/top/above-mouth and avoid overlapping >10% of face bbox.
    """

    # Keep subtitles higher than the TikTok UI (buttons/captions) which often cover the lower third.
    bottom_margin = int(max(play_res_y * 0.14, 240))
    top_margin = int(max(play_res_y * 0.08, 120))

    frames = _extract_frames(
        video_path=source_video,
        start_seconds=clip_start_seconds,
        end_seconds=clip_end_seconds,
        work_dir=work_dir,
    )

    face_bboxes, mouth_ymin = _detect_faces_and_mouth_ymin_rel(frames[:5])

    ui_score = 0.0
    try:
        import cv2

        if frames:
            img = cv2.imread(str(frames[len(frames) // 2]))
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                h, w = gray.shape[:2]
                # Heuristic: edge density in bottom third and corners.
                bottom = _edge_density(gray, x0=0, y0=int(h * 0.70), x1=w, y1=h)
                tl = _edge_density(gray, x0=0, y0=0, x1=int(w * 0.20), y1=int(h * 0.20))
                tr = _edge_density(gray, x0=int(w * 0.80), y0=0, x1=w, y1=int(h * 0.20))
                ui_score = max(bottom, tl, tr)
    except Exception:
        ui_score = 0.0

    # Approx subtitle box height (2 lines + padding).
    box_h = int(play_res_y * 0.14)

    candidates: list[SubtitlePlacement] = []

    # bottom-center
    candidates.append(SubtitlePlacement(alignment=2, x=play_res_x // 2, y=play_res_y - bottom_margin))

    # top-center
    candidates.append(SubtitlePlacement(alignment=8, x=play_res_x // 2, y=top_margin))

    # above-mouth (anchor bottom-center)
    if mouth_ymin is not None:
        y = int(mouth_ymin * play_res_y) - int(max(play_res_y * 0.03, 70))
        y = max(top_margin + box_h, min(play_res_y - bottom_margin, y))
        candidates.append(SubtitlePlacement(alignment=2, x=play_res_x // 2, y=y))

    if not face_bboxes:
        # No faces: use bottom-center but if UI score suggests lower-third graphics, push up a bit.
        if ui_score > 0.12:
            shift = int(max(play_res_y * 0.05, 70))
            return SubtitlePlacement(
                alignment=2,
                x=play_res_x // 2,
                y=play_res_y - bottom_margin - shift,
                face_overlap_ratio=0.0,
                ui_overlap_ratio=0.0,
                ui_score=ui_score,
            )
        c = candidates[0]
        return SubtitlePlacement(
            alignment=c.alignment,
            x=c.x,
            y=c.y,
            face_overlap_ratio=0.0,
            ui_overlap_ratio=0.0,
            ui_score=ui_score,
        )

    def face_overlap_proxy(placement: SubtitlePlacement) -> float:
        # Fast proxy (single aggregated bbox) used only when CV deps are missing.
        if placement.alignment == 8:
            y0 = placement.y
            y1 = placement.y + box_h
        else:
            y0 = placement.y - box_h
            y1 = placement.y

        y0_rel = y0 / play_res_y
        y1_rel = y1 / play_res_y

        sub_x0 = 0.08
        sub_x1 = 0.92

        worst = 0.0
        for xmin, ymin, xmax, ymax in face_bboxes:
            inter_y = max(0.0, min(y1_rel, ymax) - max(y0_rel, ymin))
            inter_x = max(0.0, min(sub_x1, xmax) - max(sub_x0, xmin))
            inter = inter_x * inter_y
            area = max(1e-6, (xmax - xmin) * (ymax - ymin))
            worst = max(worst, inter / area)
        return worst

    best = None
    best_score = -1e9

    # Compute p95 overlap metrics per candidate when frames exist.
    # This is best-effort: if CV deps are missing, we fall back to the proxy.
    face_p95_by_candidate: list[float] = []
    ui_p95_by_candidate: list[float] = []

    if frames:
        for c in candidates:
            f95, u95 = _compute_overlap_metrics(
                frame_paths=frames,
                placement=c,
                play_res_x=play_res_x,
                play_res_y=play_res_y,
                box_h_px=box_h,
                ui_safe_ymin=ui_safe_ymin,
            )
            face_p95_by_candidate.append(f95)
            ui_p95_by_candidate.append(u95)
    else:
        for c in candidates:
            face_p95_by_candidate.append(face_overlap_proxy(c))
            ui_p95_by_candidate.append(0.0)

    for idx, c in enumerate(candidates):
        face_p95 = face_p95_by_candidate[idx]
        ui_p95 = ui_p95_by_candidate[idx]

        # Penalize face overlap heavily, then UI overlap.
        score = 1.0 - 4.0 * face_p95 - 2.5 * ui_p95

        # Keep the heuristic score as a weak prior.
        if c.alignment == 2:
            score -= 0.75 * ui_score
            score += 0.1

        if score > best_score:
            best_score = score
            best = c

    if best is None:
        c = candidates[0]
        f95, u95 = (face_p95_by_candidate[0], ui_p95_by_candidate[0]) if face_p95_by_candidate else (0.0, 0.0)
        return SubtitlePlacement(
            alignment=c.alignment,
            x=c.x,
            y=c.y,
            face_overlap_ratio=f95,
            ui_overlap_ratio=u95,
            ui_score=ui_score,
        )

    chosen_idx = candidates.index(best)
    face_p95 = face_p95_by_candidate[chosen_idx]
    ui_p95 = ui_p95_by_candidate[chosen_idx]

    # Safety: if we chose bottom and the measured UI overlap is non-zero, shift up.
    if best.alignment == 2 and ui_p95 > 0.0:
        shift_step = int(max(play_res_y * 0.05, 70))
        best = SubtitlePlacement(
            alignment=2,
            x=best.x,
            y=max(top_margin + box_h, best.y - shift_step),
        )
        face_p95, ui_p95 = _compute_overlap_metrics(
            frame_paths=frames,
            placement=best,
            play_res_x=play_res_x,
            play_res_y=play_res_y,
            box_h_px=box_h,
            ui_safe_ymin=ui_safe_ymin,
        )

    # Safety: if face overlap is still too high, shift up once.
    if best.alignment == 2 and face_p95 > 0.10:
        shift = int(max(play_res_y * 0.05, 70))
        best = SubtitlePlacement(alignment=2, x=best.x, y=max(top_margin + box_h, best.y - shift))
        face_p95, ui_p95 = _compute_overlap_metrics(
            frame_paths=frames,
            placement=best,
            play_res_x=play_res_x,
            play_res_y=play_res_y,
            box_h_px=box_h,
            ui_safe_ymin=ui_safe_ymin,
        )

    best = SubtitlePlacement(
        alignment=best.alignment,
        x=best.x,
        y=best.y,
        face_overlap_ratio=face_p95,
        ui_overlap_ratio=ui_p95,
        ui_score=ui_score,
    )

    logger.info(
        "subtitles.placement",
        alignment=best.alignment,
        x=best.x,
        y=best.y,
        ui_score=ui_score,
        face_overlap_ratio=face_p95,
        ui_overlap_ratio=ui_p95,
        face_detected=True,
    )

    return best
