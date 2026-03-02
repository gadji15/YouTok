from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioWindowFeatures:
    rms: float
    silence_ratio: float


def compute_audio_window_features(
    *,
    wav_path: Path,
    start_seconds: float,
    end_seconds: float,
    frame_seconds: float = 0.05,
    silence_rms_threshold: float = 0.01,
) -> AudioWindowFeatures | None:
    """Compute simple audio features on a [start,end] window.

    Assumes wav is mono 16-bit PCM (as produced by our ffmpeg extract step).

    Returns None if the file cannot be read.
    """

    try:
        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            if n_channels != 1 or sampwidth != 2:
                return None

            start = max(0, int(start_seconds * sr))
            end = max(start, int(end_seconds * sr))
            total = end - start
            if total <= 0:
                return None

            wf.setpos(start)
            raw = wf.readframes(total)

        # Interpret as signed 16-bit little endian.
        import array

        arr = array.array("h")
        arr.frombytes(raw)
        if not arr:
            return None

        # RMS over full window
        mean_sq = sum((x * x for x in arr)) / float(len(arr))
        rms = math.sqrt(mean_sq) / 32768.0

        # Silence ratio over frames
        frame_len = max(1, int(frame_seconds * sr))
        silent_frames = 0
        frames = 0
        for i in range(0, len(arr), frame_len):
            chunk = arr[i : i + frame_len]
            if not chunk:
                continue
            mean_sq_c = sum((x * x for x in chunk)) / float(len(chunk))
            rms_c = math.sqrt(mean_sq_c) / 32768.0
            frames += 1
            if rms_c < silence_rms_threshold:
                silent_frames += 1

        silence_ratio = (silent_frames / frames) if frames else 0.0

        return AudioWindowFeatures(rms=float(rms), silence_ratio=float(silence_ratio))
    except Exception:
        return None


def compute_motion_score(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    sample_fps: float = 2.0,
) -> float | None:
    """Compute a cheap motion score based on frame diffs.

    Returns a value ~[0..1]. Requires opencv-python.
    """

    try:
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None

        duration = max(0.0, end_seconds - start_seconds)
        if duration <= 0.1:
            return None

        step = 1.0 / sample_fps
        t = start_seconds

        prev = None
        diffs: list[float] = []

        while t < end_seconds:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                t += step
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (160, 90))

            if prev is not None:
                diff = cv2.absdiff(prev, gray)
                diffs.append(float(diff.mean()) / 255.0)
            prev = gray
            t += step

        cap.release()

        if not diffs:
            return None

        # Normalize: values are typically small; scale up a bit then clamp.
        score = min(1.0, (sum(diffs) / len(diffs)) * 5.0)
        return float(max(0.0, score))
    except Exception:
        return None


def find_first_non_silent_time(
    *,
    wav_path: Path,
    start_seconds: float,
    end_seconds: float,
    frame_seconds: float = 0.02,
    silence_rms_threshold: float = 0.01,
) -> float | None:
    try:
        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            if n_channels != 1 or sampwidth != 2:
                return None

            start = max(0, int(start_seconds * sr))
            end = max(start, int(end_seconds * sr))
            total = end - start
            if total <= 0:
                return None

            wf.setpos(start)
            raw = wf.readframes(total)

        import array

        arr = array.array("h")
        arr.frombytes(raw)
        if not arr:
            return None

        frame_len = max(1, int(frame_seconds * sr))
        for idx in range(0, len(arr), frame_len):
            chunk = arr[idx : idx + frame_len]
            if not chunk:
                continue
            mean_sq = sum((x * x for x in chunk)) / float(len(chunk))
            rms = math.sqrt(mean_sq) / 32768.0
            if rms >= silence_rms_threshold:
                t = start_seconds + (idx / float(sr))
                return float(max(start_seconds, min(end_seconds, t)))

        return None
    except Exception:
        return None


def find_last_non_silent_time(
    *,
    wav_path: Path,
    start_seconds: float,
    end_seconds: float,
    frame_seconds: float = 0.02,
    silence_rms_threshold: float = 0.01,
) -> float | None:
    try:
        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            if n_channels != 1 or sampwidth != 2:
                return None

            start = max(0, int(start_seconds * sr))
            end = max(start, int(end_seconds * sr))
            total = end - start
            if total <= 0:
                return None

            wf.setpos(start)
            raw = wf.readframes(total)

        import array

        arr = array.array("h")
        arr.frombytes(raw)
        if not arr:
            return None

        frame_len = max(1, int(frame_seconds * sr))
        last_t = None
        for idx in range(0, len(arr), frame_len):
            chunk = arr[idx : idx + frame_len]
            if not chunk:
                continue
            mean_sq = sum((x * x for x in chunk)) / float(len(chunk))
            rms = math.sqrt(mean_sq) / 32768.0
            if rms >= silence_rms_threshold:
                last_t = start_seconds + ((idx + len(chunk)) / float(sr))

        if last_t is None:
            return None

        return float(max(start_seconds, min(end_seconds, last_t)))
    except Exception:
        return None


def compute_face_presence_score(
    *,
    video_path: Path,
    start_seconds: float,
    end_seconds: float,
    sample_fps: float = 1.0,
    max_samples: int = 8,
) -> float | None:
    """Return a face presence ratio in [0..1] based on sparse sampling.

    Best-effort: returns None if OpenCV/MediaPipe isn't available.
    """

    try:
        import cv2
        import mediapipe as mp
    except Exception:
        return None

    duration = max(0.0, end_seconds - start_seconds)
    if duration <= 0.25:
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    detector = None
    try:
        detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )

        step = max(1.0 / max(0.1, sample_fps), duration / float(max(1, max_samples)))

        t = float(start_seconds)
        total = 0
        hits = 0
        while t < end_seconds and total < max_samples:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                t += step
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = detector.process(rgb)
            total += 1
            if res.detections:
                hits += 1

            t += step

        if total <= 0:
            return None

        return float(hits / float(total))
    except Exception:
        return None
    finally:
        try:
            cap.release()
        finally:
            if detector is not None:
                try:
                    detector.close()
                except Exception:
                    pass
