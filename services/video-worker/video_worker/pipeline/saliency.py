from __future__ import annotations

from pathlib import Path


def _centroid_and_peakiness(energy: list[float]) -> tuple[float, float] | None:
    if not energy:
        return None

    total = float(sum(energy))
    if total <= 0:
        return None

    w = len(energy)
    cx = sum((i + 0.5) * float(e) for i, e in enumerate(energy)) / total

    mean = total / float(max(1, w))
    peak = float(max(energy)) / float(max(1e-9, mean))

    return float(cx / float(w)), peak


def estimate_motion_center_x_with_confidence(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    work_dir: Path,
) -> tuple[float, float] | None:
    """Estimate a horizontal center based on motion.

    Returns (x_rel, peakiness) where peakiness is roughly max/mean of the motion-energy
    per column (higher means the motion is concentrated rather than uniform).
    """

    try:
        import shutil
        import uuid

        import cv2
    except Exception:
        return None

    work_dir.mkdir(parents=True, exist_ok=True)

    frames_dir = work_dir / f"frames_{uuid.uuid4().hex}"
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

        for p in frame_paths:
            img = cv2.imread(str(p))
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            if prev is None:
                prev = gray
                _, w = gray.shape[:2]
                energy = [0.0 for _ in range(w)]
                continue

            diff = cv2.absdiff(gray, prev)
            prev = gray

            # Sum motion energy per column.
            col = diff.sum(axis=0)
            for i, v in enumerate(col.tolist()):
                energy[i] += float(v)

        if not energy:
            return None

        return _centroid_and_peakiness(energy)
    except Exception:
        return None
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)


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

    We ignore low-confidence signals (uniform motion across the whole frame), since
    that tends to "recentre" the crop and can cut off static subjects on the sides.
    """

    res = estimate_motion_center_x_with_confidence(
        video_path=video_path,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        work_dir=work_dir,
    )

    if res is None:
        return None

    cx, peak = res
    if peak < 1.12:
        return None

    return float(cx)


def estimate_edge_center_x_with_confidence(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    work_dir: Path,
) -> tuple[float, float] | None:
    """Estimate a horizontal center based on edge density.

    This is useful for cases where the subject is static (e.g. a still photo) and the
    background is animated, which can fool a motion-only estimator.

    Returns (x_rel, peakiness).
    """

    try:
        import shutil
        import uuid

        import cv2
    except Exception:
        return None

    work_dir.mkdir(parents=True, exist_ok=True)

    frames_dir = work_dir / f"frames_{uuid.uuid4().hex}"
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
        if not frame_paths:
            return None

        energy = None

        for p in frame_paths:
            img = cv2.imread(str(p))
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            if energy is None:
                _, w = gray.shape[:2]
                energy = [0.0 for _ in range(w)]

            gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            gx = cv2.abs(gx)

            col = gx.sum(axis=0)
            for i, v in enumerate(col.tolist()):
                energy[i] += float(v)

        if not energy:
            return None

        return _centroid_and_peakiness(energy)
    except Exception:
        return None
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)


def estimate_edge_center_x(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    work_dir: Path,
) -> float | None:
    res = estimate_edge_center_x_with_confidence(
        video_path=video_path,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        work_dir=work_dir,
    )

    if res is None:
        return None

    cx, peak = res
    if peak < 1.08:
        return None

    return float(cx)
