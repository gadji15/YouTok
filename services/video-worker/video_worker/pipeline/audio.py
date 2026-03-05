from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

from ..utils.retry import retry
from ..utils.subprocess import run


def extract_audio_wav(
    *,
    input_video: Path,
    output_wav: Path,
    logger: structlog.BoundLogger,
    normalize: bool = True,
    denoise: bool = True,
    max_retries: int = 1,
) -> Path:
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    if output_wav.exists() and output_wav.stat().st_size > 0:
        logger.info("audio.skip", path=str(output_wav))
        return output_wav

    filters: list[str] = []

    # Light speech-prep filters for transcription quality.
    # Keep this conservative: the goal is to improve intelligibility, not to "master" audio.
    if denoise:
        filters.append("highpass=f=80")
        filters.append("lowpass=f=8000")
        filters.append("afftdn=nr=10:nf=-50")

    if normalize:
        filters.append("dynaudnorm=f=150:g=5")

    def _should_retry(exc: Exception) -> bool:
        return isinstance(exc, subprocess.CalledProcessError)

    def _do_extract() -> None:
        args = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_video),
            "-map",
            "a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
        ]

        if filters:
            args += ["-af", ",".join(filters)]

        args += [
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ]

        run(args, logger=logger)

    retry(
        _do_extract,
        should_retry=_should_retry,
        max_retries=max(0, int(max_retries)),
        backoff_seconds=0.5,
        logger=logger,
        log_event="audio.retry",
    )

    logger.info("audio.done", path=str(output_wav), size_bytes=output_wav.stat().st_size)
    return output_wav
