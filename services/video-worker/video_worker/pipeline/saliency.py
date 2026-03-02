from __future__ import annotations

from pathlib import Path


def estimate_motion_center_x(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    work_dir: Path,
) -> float | None:
    """Estimate an interesting horizontal center based on motion.

    Returns a relative X coordinate in [0..1]. If OpenCV/ffmpeg isn't available or
    no usable motion signal is found, returns None.
    """

    try:
        import shutil

        import cv2
    except Exception:
        return None

    frames_dir = work_dir / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    try:
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
                "fps=2,scale=640:-1",
                str(frames_dir / "frame_%04d.jpg"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        frame_paths = sorted(frames_dir.glob("frame_*.jpg"))
        if len(frame_paths) < 2:
            return None

        prev = None
        energy = None
        w = None

        for p in frame_paths:
            img = cv2.imread(str(p))
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            if prev is None:
                prev = gray
                h, w = gray.shape[:2]
                energy = [0.0 for _ in range(w)]
                continue

            diff = cv2.absdiff(gray, prev)
            prev = gray

            # Sum motion energy per column.
            col = diff.sum(axis=0)
            for i, v in enumerate(col.tolist()):
                energy[i] += float(v)

        if not energy or w is None:
            return None

        total = sum(energy)
        if total <= 0:
            return None

        cx = sum((i + 0.5) * e for i, e in enumerate(energy)) / total
        return float(cx / float(w))
    except Exception:
        return None
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)
