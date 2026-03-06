from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import json
import math
import time

import structlog

from ..utils.subprocess import run


@dataclass(frozen=True)
class TextAwareCropConfig:
    out_w: int = 1080
    out_h: int = 1920

    sample_fps: float = 2.0
    padding_ratio: float = 0.18

    ocr_lang: str = "eng+fra+ara"
    ocr_conf_threshold: float = 60.0

    min_zoom: float = 1.0
    max_zoom: float = 1.9

    reading_hold_sec: float = 0.8

    smoother_min_cutoff: float = 1.0
    smoother_beta: float = 0.0

    debug_frames: bool = False
    debug_frame_stride: int = 10


@dataclass(frozen=True)
class _FrameTarget:
    cx: float
    cy: float
    zoom: float


def _clamp(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, v)))


def union_boxes(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return int(x0), int(y0), int(x1), int(y1)


def pad_and_fix_ratio(
    *,
    box: tuple[int, int, int, int],
    frame_w: int,
    frame_h: int,
    out_w: int,
    out_h: int,
    pad_ratio: float,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box

    x0 = int(_clamp(float(x0), 0.0, float(frame_w)))
    y0 = int(_clamp(float(y0), 0.0, float(frame_h)))
    x1 = int(_clamp(float(x1), 0.0, float(frame_w)))
    y1 = int(_clamp(float(y1), 0.0, float(frame_h)))

    bw = max(1, x1 - x0)
    bh = max(1, y1 - y0)

    padx = int(round(bw * float(pad_ratio)))
    pady = int(round(bh * float(pad_ratio)))

    x0 = max(0, x0 - padx)
    y0 = max(0, y0 - pady)
    x1 = min(frame_w, x1 + padx)
    y1 = min(frame_h, y1 + pady)

    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0

    bw = max(2, x1 - x0)
    bh = max(2, y1 - y0)

    target_ar = float(out_w) / float(out_h)
    cur_ar = float(bw) / float(bh)

    if cur_ar > target_ar:
        # too wide -> expand height
        new_w = float(bw)
        new_h = new_w / target_ar
    else:
        # too tall -> expand width
        new_h = float(bh)
        new_w = new_h * target_ar

    new_w = min(float(frame_w), max(2.0, new_w))
    new_h = min(float(frame_h), max(2.0, new_h))

    # Ensure within bounds by shifting the center if needed.
    x0f = cx - new_w / 2.0
    y0f = cy - new_h / 2.0

    x0f = _clamp(x0f, 0.0, float(frame_w) - new_w)
    y0f = _clamp(y0f, 0.0, float(frame_h) - new_h)

    x1f = x0f + new_w
    y1f = y0f + new_h

    return int(round(x0f)), int(round(y0f)), int(round(x1f)), int(round(y1f))


def _base_crop_size(*, frame_w: int, frame_h: int, out_w: int, out_h: int) -> tuple[int, int]:
    target_ar = float(out_w) / float(out_h)
    a_src = float(frame_w) / float(frame_h)

    if a_src >= target_ar:
        # crop horizontally
        crop_h = frame_h
        crop_w = int(round(float(frame_h) * target_ar))
    else:
        # crop vertically (rare for already-vertical sources)
        crop_w = frame_w
        crop_h = int(round(float(frame_w) / target_ar))

    crop_w = max(2, min(frame_w, int(crop_w)))
    crop_h = max(2, min(frame_h, int(crop_h)))

    return crop_w, crop_h


def _interpolate_targets(
    *,
    targets: list[_FrameTarget | None],
    default: _FrameTarget,
) -> list[_FrameTarget]:
    n = len(targets)
    if n == 0:
        return []

    out: list[_FrameTarget] = [default for _ in range(n)]

    # Gather known indices.
    known = [(i, t) for i, t in enumerate(targets) if t is not None]
    if not known:
        return out

    for i, t in known:
        out[i] = t

    # Forward fill for head.
    first_i, first_t = known[0]
    for i in range(0, first_i):
        out[i] = first_t

    # Back fill for tail.
    last_i, last_t = known[-1]
    for i in range(last_i + 1, n):
        out[i] = last_t

    # Linear interpolate between known points.
    for (i0, t0), (i1, t1) in zip(known, known[1:]):
        if i1 <= i0 + 1:
            continue
        span = float(i1 - i0)
        for i in range(i0 + 1, i1):
            u = float(i - i0) / span
            out[i] = _FrameTarget(
                cx=(t0.cx * (1.0 - u)) + (t1.cx * u),
                cy=(t0.cy * (1.0 - u)) + (t1.cy * u),
                zoom=(t0.zoom * (1.0 - u)) + (t1.zoom * u),
            )

    return out


class _LowPass:
    def __init__(self, alpha: float, init: float | None = None) -> None:
        self.alpha = float(alpha)
        self.y = float(init) if init is not None else None

    def apply(self, x: float) -> float:
        if self.y is None:
            self.y = float(x)
            return float(x)

        a = float(_clamp(self.alpha, 0.0, 1.0))
        self.y = (a * float(x)) + ((1.0 - a) * float(self.y))
        return float(self.y)

    def apply_with_alpha(self, x: float, alpha: float) -> float:
        self.alpha = float(alpha)
        return self.apply(x)


def _alpha(*, freq: float, cutoff: float) -> float:
    freq = max(1e-3, float(freq))
    cutoff = max(1e-3, float(cutoff))
    te = 1.0 / freq
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + (tau / te))


class OneEuroFilter:
    def __init__(self, *, freq: float, min_cutoff: float = 1.0, beta: float = 0.0, d_cutoff: float = 1.0) -> None:
        self.freq = float(freq)
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)

        self._x = _LowPass(alpha=1.0)
        self._dx = _LowPass(alpha=1.0)

    def apply(self, x: float) -> float:
        # Fixed-step variant: freq is constant (video frame rate).
        dx = 0.0
        if self._x.y is not None:
            dx = (float(x) - float(self._x.y)) * float(self.freq)

        a_d = _alpha(freq=self.freq, cutoff=self.d_cutoff)
        edx = self._dx.apply_with_alpha(dx, a_d)

        cutoff = float(self.min_cutoff) + float(self.beta) * abs(float(edx))
        a = _alpha(freq=self.freq, cutoff=cutoff)
        return self._x.apply_with_alpha(x, a)


class _FaceDetector:
    def __init__(self) -> None:
        self._cv2 = None
        self._det = None

        try:
            import cv2
            import mediapipe as mp

            if getattr(mp, "solutions", None) and getattr(mp.solutions, "face_detection", None):
                self._cv2 = cv2
                self._det = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
        except Exception:
            self._cv2 = None
            self._det = None

    def close(self) -> None:
        try:
            if self._det is not None:
                self._det.close()
        except Exception:
            pass

        self._det = None

    def detect(self, frame_bgr) -> tuple[int, int, int, int] | None:
        if self._cv2 is None or self._det is None:
            return None

        cv2 = self._cv2
        h, w = frame_bgr.shape[:2]
        if h <= 0 or w <= 0:
            return None

        try:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            res = self._det.process(rgb)
            if not res.detections:
                return None

            best = None
            best_score = -1.0

            for d in res.detections:
                try:
                    bbox = d.location_data.relative_bounding_box
                    area = float(max(0.0, bbox.width) * max(0.0, bbox.height))
                    conf = float(d.score[0]) if getattr(d, "score", None) else 0.0
                    score = area * (0.5 + conf)
                except Exception:
                    continue

                if score > best_score:
                    best = d
                    best_score = score

            if best is None:
                return None

            bbox = best.location_data.relative_bounding_box
            x0 = int(round(float(bbox.xmin) * w))
            y0 = int(round(float(bbox.ymin) * h))
            x1 = int(round(float(bbox.xmin + bbox.width) * w))
            y1 = int(round(float(bbox.ymin + bbox.height) * h))

            x0 = int(_clamp(float(x0), 0.0, float(w)))
            y0 = int(_clamp(float(y0), 0.0, float(h)))
            x1 = int(_clamp(float(x1), 0.0, float(w)))
            y1 = int(_clamp(float(y1), 0.0, float(h)))

            if x1 <= x0 or y1 <= y0:
                return None

            return x0, y0, x1, y1
        except Exception:
            return None


def _is_texty(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return False

    for ch in t:
        o = ord(ch)
        if ch.isalnum():
            return True
        # Arabic blocks
        if 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0x08A0 <= o <= 0x08FF:
            return True

    return False


def _detect_text_box(frame_bgr, *, cfg: TextAwareCropConfig) -> tuple[tuple[int, int, int, int] | None, str, float]:
    try:
        import cv2
        import numpy as np
        import pytesseract
    except Exception:
        return None, "", -1.0

    h, w = frame_bgr.shape[:2]
    if h <= 0 or w <= 0:
        return None, "", -1.0

    # Downscale for speed.
    target_w = 640
    scale = min(1.0, float(target_w) / float(w))
    if scale < 1.0:
        small = cv2.resize(frame_bgr, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA)
    else:
        small = frame_bgr

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    try:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    except Exception:
        bw = gray

    data = pytesseract.image_to_data(bw, output_type=pytesseract.Output.DICT, lang=cfg.ocr_lang)

    texts: list[str] = []
    confs: list[float] = []
    boxes: list[tuple[int, int, int, int]] = []

    n = len(data.get("text") or [])
    for i in range(n):
        txt = str((data.get("text") or [""])[i] or "").strip()
        if not _is_texty(txt):
            continue

        conf_raw = (data.get("conf") or [""])[i]
        try:
            conf = float(conf_raw)
        except Exception:
            conf = -1.0

        if conf < float(cfg.ocr_conf_threshold):
            continue

        left = int((data.get("left") or [0])[i])
        top = int((data.get("top") or [0])[i])
        ww = int((data.get("width") or [0])[i])
        hh = int((data.get("height") or [0])[i])
        if ww <= 0 or hh <= 0:
            continue

        x0 = int(round(float(left) / scale))
        y0 = int(round(float(top) / scale))
        x1 = int(round(float(left + ww) / scale))
        y1 = int(round(float(top + hh) / scale))

        x0 = int(_clamp(float(x0), 0.0, float(w)))
        y0 = int(_clamp(float(y0), 0.0, float(h)))
        x1 = int(_clamp(float(x1), 0.0, float(w)))
        y1 = int(_clamp(float(y1), 0.0, float(h)))

        if x1 <= x0 or y1 <= y0:
            continue

        boxes.append((x0, y0, x1, y1))
        texts.append(txt)
        confs.append(conf)

    if not boxes:
        return None, "", -1.0

    u = union_boxes(boxes)
    if u is None:
        return None, "", -1.0

    joined = " ".join(texts).strip()
    avg_conf = float(np.mean(confs)) if confs else -1.0

    return u, joined, avg_conf


def _compute_text_segments(
    *,
    text_present: list[bool],
    frame_count: int,
    fps: float,
    ocr_text_by_sample_frame: dict[int, str],
    ocr_conf_by_sample_frame: dict[int, float],
) -> list[dict]:
    segments: list[dict] = []

    i = 0
    while i < frame_count:
        if not text_present[i]:
            i += 1
            continue

        j = i
        while j < frame_count and text_present[j]:
            j += 1

        start_time = float(i) / float(max(1e-3, fps))
        end_time = float(j) / float(max(1e-3, fps))

        texts: list[str] = []
        confs: list[float] = []
        for k, txt in ocr_text_by_sample_frame.items():
            if i <= k < j:
                t = (txt or "").strip()
                if t:
                    texts.append(t)

        for k, c in ocr_conf_by_sample_frame.items():
            if i <= k < j:
                try:
                    confs.append(float(c))
                except Exception:
                    continue

        segments.append(
            {
                "start_time": start_time,
                "end_time": end_time,
                "ocr_text": " ".join(texts).strip(),
                "avg_conf": float(sum(confs) / len(confs)) if confs else None,
            }
        )

        i = j

    return segments


def render_text_aware_crop(
    *,
    source_video: Path,
    start_seconds: float,
    end_seconds: float,
    output_video: Path,
    output_dir: Path,
    cfg: TextAwareCropConfig,
    logger: structlog.BoundLogger,
    target_fps: int = 30,
) -> dict:
    """Render a text-aware vertical crop for a clip.

    Produces:
    - output_video (1080x1920 mp4)
    - output_dir/crop_keyframes.json
    - output_dir/metrics.json

    Resume-safe: if output_video exists and is non-empty, skip work.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    keyframes_path = output_dir / "crop_keyframes.json"
    metrics_path = output_dir / "metrics.json"

    if output_video.exists() and output_video.stat().st_size > 0 and keyframes_path.exists() and keyframes_path.stat().st_size > 0:
        return {
            "video_path": str(output_video),
            "crop_keyframes_path": str(keyframes_path),
            "metrics_path": str(metrics_path) if (metrics_path.exists() and metrics_path.stat().st_size > 0) else None,
        }

    t0 = time.time()

    duration = max(0.0, float(end_seconds) - float(start_seconds))
    if duration <= 0.05:
        raise ValueError("clip_duration_too_small")

    tmp_src = output_dir / "clip_src.mp4"
    tmp_noaudio = output_dir / "video_noaudio.mp4"

    build_src_cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(float(start_seconds)),
        "-i",
        str(source_video),
        "-t",
        str(duration),
        "-vsync",
        "cfr",
        "-r",
        str(int(target_fps)),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        str(tmp_src),
    ]

    # Step 1: build a CFR source clip to stabilize frame indexing.
    if not tmp_src.exists() or tmp_src.stat().st_size <= 0:
        run(build_src_cmd, logger=logger.bind(step="text_aware_crop_build_src"))

    # Step 2: analyze sampled frames.
    try:
        import cv2
    except Exception as e:
        raise RuntimeError(f"opencv_required_for_text_aware_crop: {e}")

    cap = cv2.VideoCapture(str(tmp_src))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or float(target_fps) or 30.0)
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    if frame_w <= 0 or frame_h <= 0 or frame_count <= 0:
        cap.release()

        # We've seen resume-safe tmp clips get corrupted (e.g. incomplete moov atom).
        # Best-effort recovery: delete and rebuild once.
        try:
            tmp_src.unlink(missing_ok=True)
        except Exception:
            pass

        run(build_src_cmd, logger=logger.bind(step="text_aware_crop_rebuild_src"))

        cap = cv2.VideoCapture(str(tmp_src))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or float(target_fps) or 30.0)
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if frame_w <= 0 or frame_h <= 0 or frame_count <= 0:
            cap.release()
            raise RuntimeError("failed_to_read_video_metadata")

    sample_step = max(1, int(round(float(fps) / max(0.1, float(cfg.sample_fps)))))

    base_w, base_h = _base_crop_size(frame_w=frame_w, frame_h=frame_h, out_w=cfg.out_w, out_h=cfg.out_h)
    default_target = _FrameTarget(cx=float(frame_w) / 2.0, cy=float(frame_h) / 2.0, zoom=float(cfg.min_zoom))

    sampled: list[_FrameTarget | None] = [None for _ in range(frame_count)]
    sampled_text_present: list[bool | None] = [None for _ in range(frame_count)]
    ocr_text_by_sample_frame: dict[int, str] = {}
    ocr_conf_by_sample_frame: dict[int, float] = {}

    debug_dir = output_dir / "debug_frames"
    if cfg.debug_frames:
        debug_dir.mkdir(parents=True, exist_ok=True)

    face_detector = _FaceDetector()

    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if idx % sample_step == 0:
            text_box, ocr_text, ocr_conf = _detect_text_box(frame, cfg=cfg)
            face_box = None
            if text_box is None:
                face_box = face_detector.detect(frame)

            chosen = text_box or face_box

            if chosen is None:
                rect_w = base_w
                cx = float(frame_w) / 2.0
                cy = float(frame_h) / 2.0
            else:
                x0, y0, x1, y1 = pad_and_fix_ratio(
                    box=chosen,
                    frame_w=frame_w,
                    frame_h=frame_h,
                    out_w=cfg.out_w,
                    out_h=cfg.out_h,
                    pad_ratio=cfg.padding_ratio,
                )
                rect_w = max(2, x1 - x0)
                cx = (x0 + x1) / 2.0
                cy = (y0 + y1) / 2.0

            zoom = float(base_w) / float(max(2, rect_w))
            zoom = _clamp(zoom, float(cfg.min_zoom), float(cfg.max_zoom))

            sampled[idx] = _FrameTarget(cx=float(cx), cy=float(cy), zoom=float(zoom))

            text_ok = text_box is not None and float(ocr_conf) >= float(cfg.ocr_conf_threshold)
            sampled_text_present[idx] = bool(text_ok)

            if text_ok:
                ocr_text_by_sample_frame[idx] = str(ocr_text or "")
                ocr_conf_by_sample_frame[idx] = float(ocr_conf)

            if cfg.debug_frames and (idx // sample_step) % max(1, int(cfg.debug_frame_stride)) == 0:
                try:
                    dbg = frame.copy()
                    if text_box is not None:
                        cv2.rectangle(dbg, (text_box[0], text_box[1]), (text_box[2], text_box[3]), (0, 255, 255), 2)
                    if face_box is not None:
                        cv2.rectangle(dbg, (face_box[0], face_box[1]), (face_box[2], face_box[3]), (255, 0, 0), 2)
                    cv2.putText(
                        dbg,
                        f"conf={ocr_conf:.1f}",
                        (12, 36),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (255, 255, 255),
                        2,
                    )
                    cv2.imwrite(str(debug_dir / f"frame_{idx:06d}.jpg"), dbg)
                except Exception:
                    pass

        idx += 1

    cap.release()
    face_detector.close()

    targets = _interpolate_targets(targets=sampled, default=default_target)

    # Expand sampled_text_present to all frames (nearest neighbor).
    text_present: list[bool] = [False for _ in range(frame_count)]
    last = False
    for i in range(frame_count):
        if sampled_text_present[i] is not None:
            last = bool(sampled_text_present[i])
        text_present[i] = last

    # Detect reading-mode segments.
    reading_mode: list[bool] = [False for _ in range(frame_count)]
    hold_frames = int(round(float(cfg.reading_hold_sec) * float(fps)))
    if hold_frames < 1:
        hold_frames = 1

    i = 0
    while i < frame_count:
        if not text_present[i]:
            i += 1
            continue
        j = i
        while j < frame_count and text_present[j]:
            j += 1
        if (j - i) >= hold_frames:
            for k in range(i, j):
                reading_mode[k] = True
        i = j

    # Step 3: smooth.
    cx_f = OneEuroFilter(freq=fps, min_cutoff=cfg.smoother_min_cutoff, beta=cfg.smoother_beta)
    cy_f = OneEuroFilter(freq=fps, min_cutoff=cfg.smoother_min_cutoff, beta=cfg.smoother_beta)
    z_f = OneEuroFilter(freq=fps, min_cutoff=cfg.smoother_min_cutoff, beta=cfg.smoother_beta)

    smooth: list[_FrameTarget] = []
    for t in targets:
        smooth.append(
            _FrameTarget(
                cx=float(cx_f.apply(t.cx)),
                cy=float(cy_f.apply(t.cy)),
                zoom=float(z_f.apply(t.zoom)),
            )
        )

    # Reading mode stabilization: apply an extra EMA + clamp movement.
    max_pan_px = float(frame_w) * 0.02
    max_pan_py = float(frame_h) * 0.02

    for i in range(1, frame_count):
        if not reading_mode[i]:
            continue
        prev = smooth[i - 1]
        cur = smooth[i]

        dx = _clamp(cur.cx - prev.cx, -max_pan_px, max_pan_px)
        dy = _clamp(cur.cy - prev.cy, -max_pan_py, max_pan_py)

        cx = prev.cx + dx
        cy = prev.cy + dy

        zoom = (0.9 * float(prev.zoom)) + (0.1 * float(cur.zoom))

        smooth[i] = _FrameTarget(cx=float(cx), cy=float(cy), zoom=float(zoom))

    # Step 4: render via ffmpeg rawvideo pipe.
    cap2 = cv2.VideoCapture(str(tmp_src))

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{cfg.out_w}x{cfg.out_h}",
        "-r",
        str(int(target_fps)),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        str(tmp_noaudio),
    ]

    logger.info("exec", args=ffmpeg_cmd, cwd=None)

    import subprocess

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    out_ar = float(cfg.out_w) / float(cfg.out_h)

    for i in range(frame_count):
        ok, frame = cap2.read()
        if not ok:
            break

        t = smooth[i]

        crop_w = int(round(float(base_w) / float(max(1e-3, t.zoom))))
        crop_h = int(round(float(base_h) / float(max(1e-3, t.zoom))))

        crop_w = max(2, min(frame_w, crop_w))
        crop_h = max(2, min(frame_h, crop_h))

        cur_ar = float(crop_w) / float(crop_h)
        if abs(cur_ar - out_ar) > 0.01:
            if cur_ar > out_ar:
                crop_h = int(round(float(crop_w) / out_ar))
                crop_h = max(2, min(frame_h, crop_h))
            else:
                crop_w = int(round(float(crop_h) * out_ar))
                crop_w = max(2, min(frame_w, crop_w))

        x0 = int(round(float(t.cx) - float(crop_w) / 2.0))
        y0 = int(round(float(t.cy) - float(crop_h) / 2.0))

        x0 = int(_clamp(float(x0), 0.0, float(frame_w - crop_w)))
        y0 = int(_clamp(float(y0), 0.0, float(frame_h - crop_h)))

        crop = frame[y0 : y0 + crop_h, x0 : x0 + crop_w]
        out_frame = cv2.resize(crop, (cfg.out_w, cfg.out_h), interpolation=cv2.INTER_AREA)

        if proc.stdin is not None:
            proc.stdin.write(out_frame.tobytes())

    cap2.release()

    if proc.stdin is not None:
        proc.stdin.close()
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"ffmpeg_rawvideo_encode_failed: {ret}")

    # Step 5: mux audio back from tmp_src.
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(tmp_noaudio),
            "-i",
            str(tmp_src),
            "-map",
            "0:v:0",
            "-map",
            "1:a?",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_video),
        ],
        logger=logger.bind(step="text_aware_crop_mux_audio"),
    )

    frames_payload: list[dict] = []
    for i, t in enumerate(smooth):
        frames_payload.append(
            {
                "frame_index": int(i),
                "time": float(i) / float(max(1e-3, fps)),
                "cx": float(t.cx),
                "cy": float(t.cy),
                "zoom": float(_clamp(t.zoom, float(cfg.min_zoom), float(cfg.max_zoom))),
                "reading_mode": bool(reading_mode[i]),
            }
        )

    segments_text = _compute_text_segments(
        text_present=text_present,
        frame_count=frame_count,
        fps=fps,
        ocr_text_by_sample_frame=ocr_text_by_sample_frame,
        ocr_conf_by_sample_frame=ocr_conf_by_sample_frame,
    )

    keyframes_path.write_text(
        json.dumps(
            {
                "video": str(source_video),
                "clip": {"start_seconds": float(start_seconds), "end_seconds": float(end_seconds)},
                "out_resolution": [int(cfg.out_w), int(cfg.out_h)],
                "fps": float(fps),
                "frames": frames_payload,
                "segments_text": segments_text,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = {
        "processing_time_seconds": float(time.time() - t0),
        "frame_count": int(frame_count),
        "fps": float(fps),
        "sample_fps": float(cfg.sample_fps),
        "segments_detected": int(len(segments_text)),
        "avg_ocr_conf": (
            float(sum(ocr_conf_by_sample_frame.values()) / len(ocr_conf_by_sample_frame)) if ocr_conf_by_sample_frame else None
        ),
    }

    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    logger.info(
        "text_aware_crop.done",
        output_video=str(output_video),
        crop_keyframes=str(keyframes_path),
        metrics=str(metrics_path),
        frames=frame_count,
        sample_step=sample_step,
        elapsed_seconds=float(time.time() - t0),
    )

    return {
        "video_path": str(output_video),
        "crop_keyframes_path": str(keyframes_path),
        "metrics_path": str(metrics_path),
    }
