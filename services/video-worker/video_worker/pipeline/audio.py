from __future__ import annotations

from pathlib import Path

import structlog

from ..utils.subprocess import run


def extract_audio_wav(*, input_video: Path, output_wav: Path, logger: structlog.BoundLogger) -> Path:
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    if output_wav.exists() and output_wav.stat().st_size > 0:
        logger.info("audio.skip", path=str(output_wav))
        return output_wav

    run(
        [
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
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ],
        logger=logger,
    )

    logger.info("audio.done", path=str(output_wav), size_bytes=output_wav.stat().st_size)
    return output_wav
