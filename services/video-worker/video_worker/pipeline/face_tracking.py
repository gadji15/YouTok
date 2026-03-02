from __future__ import annotations

from pathlib import Path


def mediapipe_available() -> bool:
    try:
        import mediapipe  # noqa: F401

        return True
    except Exception:
        return False


def estimate_face_center_x(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    work_dir: Path,
) -> float | None:
    """Return an estimated face-center X coordinate in *relative [0..1]* space.

    If MediaPipe is not installed, ffmpeg isn't available, or no faces are detected, returns None.
    """

    try:
        import shutil

        import cv2
        import mediapipe as mp
    except Exception:
        return None

    frames_dir = work_dir / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    detector = None
    try:
        # Extract 1fps frames for the clip range.
        import subprocess

        duration = max(0.0, end_seconds - start_seconds)
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
                "fps=1,scale=640:-1",
                str(frames_dir / "frame_%04d.jpg"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )

        xs: list[float] = []
        for frame_path in sorted(frames_dir.glob("frame_*.jpg")):
            img = cv2.imread(str(frame_path))
            if img is None:
                continue
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = detector.process(rgb)
            if not res.detections:
                continue
            det = res.detections[0]
            bbox = det.location_data.relative_bounding_box
            cx_rel = (bbox.xmin + bbox.width / 2.0)
            # bbox coords are already relative to frame width.
            if 0.0 <= cx_rel <= 1.0:
                xs.append(float(cx_rel))

        if not xs:
            return None
        return float(sum(xs) / len(xs))
    except Exception:
        return None
    finally:
        try:
            if detector is not None:
                detector.close()
        finally:
            shutil.rmtree(frames_dir, ignore_errors=True)
