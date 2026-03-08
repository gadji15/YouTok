from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def mediapipe_available() -> bool:
    try:
        import mediapipe  # noqa: F401

        return True
    except Exception:
        return False


@dataclass(frozen=True)
class FaceCenterSample:
    t_seconds: float
    x_rel: float


def estimate_face_centers_x(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    work_dir: Path,
    sample_fps: float = 2.0,
) -> list[FaceCenterSample]:
    """Best-effort face-center tracking over time.

    Returns a list of (t_seconds, x_rel) samples where:
    - t_seconds is absolute time in the source video.
    - x_rel is the face center X in relative [0..1] frame coords.

    When MediaPipe isn't available or no faces are detected, returns an empty list.
    """

    try:
        import shutil
        import subprocess

        import cv2
        import mediapipe as mp
    except Exception:
        return []

    import uuid

    work_dir.mkdir(parents=True, exist_ok=True)

    frames_dir = work_dir / f"frames_{uuid.uuid4().hex}"
    frames_dir.mkdir(parents=True, exist_ok=True)

    detector = None
    try:
        duration = max(0.0, end_seconds - start_seconds)
        if duration <= 0.05:
            return []

        # Note: ffmpeg-generated frame sequence doesn't embed timestamps.
        # We reconstruct timestamps from start_seconds + index / sample_fps.
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
                f"fps={sample_fps},scale=640:-1",
                str(frames_dir / "frame_%06d.jpg"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5,
        )

        out: list[FaceCenterSample] = []

        frame_paths = sorted(frames_dir.glob("frame_*.jpg"))
        for idx, frame_path in enumerate(frame_paths):
            img = cv2.imread(str(frame_path))
            if img is None:
                continue
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = detector.process(rgb)
            if not res.detections:
                continue

            # Pick the most prominent face (helps when there are multiple detections).
            def _det_score(d) -> float:
                try:
                    bbox = d.location_data.relative_bounding_box
                    area = float(max(0.0, bbox.width) * max(0.0, bbox.height))
                    conf = float(d.score[0]) if getattr(d, "score", None) else 0.0
                    return area * (0.5 + conf)
                except Exception:
                    return 0.0

            det = max(res.detections, key=_det_score)
            bbox = det.location_data.relative_bounding_box

            cx_rel = float(bbox.xmin + bbox.width / 2.0)
            cx_rel = float(max(0.0, min(1.0, cx_rel)))

            t = float(start_seconds + (idx / max(0.001, float(sample_fps))))
            out.append(FaceCenterSample(t_seconds=t, x_rel=cx_rel))

        return out
    except Exception:
        return []
    finally:
        try:
            if detector is not None:
                detector.close()
        finally:
            shutil.rmtree(frames_dir, ignore_errors=True)


def estimate_face_center_x(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    work_dir: Path,
) -> float | None:
    """Return a robust face-center X coordinate in relative [0..1] space.

    Uses multiple frames and returns the median to reduce jitter.
    """

    samples = estimate_face_centers_x(
        video_path=video_path,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        work_dir=work_dir,
        sample_fps=2.0,
    )

    if not samples:
        return None

    xs = sorted(s.x_rel for s in samples)
    mid = len(xs) // 2
    if len(xs) % 2 == 1:
        return float(xs[mid])

    return float((xs[mid - 1] + xs[mid]) / 2.0)
