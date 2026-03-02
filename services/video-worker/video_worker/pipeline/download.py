from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

from ..utils.retry import retry
from ..utils.subprocess import run


def download_youtube_video(
    *,
    youtube_url: str,
    output_path: Path,
    logger: structlog.BoundLogger,
    max_retries: int = 2,
    retry_backoff_seconds: float = 1.0,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and output_path.stat().st_size > 0:
        logger.info("download.skip", path=str(output_path))
        return output_path

    if output_path.exists() and output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)

    def _cleanup_temp() -> None:
        for p in output_path.parent.glob(output_path.stem + ".*"):
            if p == output_path:
                continue
            p.unlink(missing_ok=True)

        # Common yt-dlp leftovers.
        for p in output_path.parent.glob(output_path.stem + ".*part"):
            p.unlink(missing_ok=True)

    _cleanup_temp()

    tmp_template = output_path.with_suffix(".%(ext)s")

    def _should_retry(exc: Exception) -> bool:
        return isinstance(exc, subprocess.CalledProcessError)

    def _do_download() -> None:
        _cleanup_temp()
        run(
            [
                "yt-dlp",
                "--no-progress",
                "--no-playlist",
                "--retries",
                "3",
                "--fragment-retries",
                "3",
                "-f",
                "bestvideo+bestaudio/best",
                "--merge-output-format",
                "mp4",
                "--force-overwrites",
                "-o",
                str(tmp_template),
                youtube_url,
            ],
            logger=logger,
        )

    retry(
        _do_download,
        should_retry=_should_retry,
        max_retries=max_retries,
        backoff_seconds=retry_backoff_seconds,
        logger=logger,
        log_event="download.retry",
    )

    candidates = sorted(output_path.parent.glob(output_path.stem + ".*"))
    if output_path in candidates:
        chosen = output_path
    else:
        mp4s = [p for p in candidates if p.suffix.lower() == ".mp4"]
        chosen = mp4s[0] if mp4s else (candidates[0] if candidates else None)

    if chosen is None or not chosen.exists() or chosen.stat().st_size <= 0:
        raise RuntimeError("yt-dlp finished but no output file was produced")

    if chosen != output_path:
        chosen.replace(output_path)

    if output_path.stat().st_size <= 0:
        raise RuntimeError("download produced an empty file")

    logger.info("download.done", path=str(output_path), size_bytes=output_path.stat().st_size)
    return output_path
