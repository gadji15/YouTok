from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog


@dataclass(frozen=True)
class SubtitlePlacement:
    alignment: int
    x: int
    y: int


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


def _detect_faces_and_mouth_ymin_rel(frame_paths: list[Path]) -> tuple[list[tuple[float, float, float, float]], float | None]:
    """Return list of face bboxes (xmin,ymin,xmax,ymax) in relative coords + mouth ymin."""

    try:
        import cv2
        import mediapipe as mp
    except Exception:
        return [], None

    # MediaPipe is an optional dependency and can be missing/partially installed on some platforms.
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

    # Approx mouth landmarks: inner+outer lips.
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


def choose_subtitle_placement(
    *,
    source_video: Path,
    clip_start_seconds: float,
    clip_end_seconds: float,
    play_res_x: int,
    play_res_y: int,
    work_dir: Path,
    logger: structlog.BoundLogger,
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

    # Approx subtitle box height (2 lines + padding) in relative coords.
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
            return SubtitlePlacement(alignment=2, x=play_res_x // 2, y=play_res_y - bottom_margin - shift)
        return candidates[0]

    def overlap_ratio(placement: SubtitlePlacement) -> float:
        # Convert subtitle box to relative bbox.
        if placement.alignment == 8:
            y0 = placement.y
            y1 = placement.y + box_h
        else:
            y0 = placement.y - box_h
            y1 = placement.y

        y0_rel = y0 / play_res_y
        y1_rel = y1 / play_res_y

        worst = 0.0
        for xmin, ymin, xmax, ymax in face_bboxes:
            inter_y = max(0.0, min(y1_rel, ymax) - max(y0_rel, ymin))
            inter_x = max(0.0, min(0.75, xmax) - max(0.25, xmin))
            inter = inter_x * inter_y
            area = max(1e-6, (xmax - xmin) * (ymax - ymin))
            worst = max(worst, inter / area)
        return worst

    best = None
    best_score = -1e9

    for c in candidates:
        o = overlap_ratio(c)
        # Penalize face overlap heavily, then UI heuristics for bottom.
        score = 1.0 - 4.0 * o
        if c.alignment == 2:
            score -= 1.5 * ui_score

        # Prefer bottom if safe.
        if c.alignment == 2:
            score += 0.1

        if score > best_score:
            best_score = score
            best = c

    if best is None:
        return candidates[0]

    # If we still chose bottom but overlap is a bit high, shift up.
    if best.alignment == 2:
        o = overlap_ratio(best)
        if o > 0.10:
            shift = int(max(play_res_y * 0.05, 70))
            best = SubtitlePlacement(alignment=2, x=best.x, y=max(top_margin + box_h, best.y - shift))

    logger.info(
        "subtitles.placement",
        alignment=best.alignment,
        x=best.x,
        y=best.y,
        ui_score=ui_score,
        face_detected=True,
    )

    return best
