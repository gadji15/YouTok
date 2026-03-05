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
    metadata_json_path: Path | None = None,
    thumbnail_path: Path | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _move_sidecars() -> None:
        if metadata_json_path is not None:
            info_candidates = sorted(output_path.parent.glob(output_path.stem + ".*.info.json"))
            if not info_candidates:
                info_candidates = sorted(output_path.parent.glob(output_path.stem + ".info.json"))

            if info_candidates:
                metadata_json_path.parent.mkdir(parents=True, exist_ok=True)
                info_candidates[0].replace(metadata_json_path)

        if thumbnail_path is not None:
            thumb_candidates: list[Path] = []
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                thumb_candidates.extend(sorted(output_path.parent.glob(output_path.stem + f".*{ext}")))
                thumb_candidates.extend(sorted(output_path.parent.glob(output_path.stem + ext)))

            if thumb_candidates:
                thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
                thumb_candidates[0].replace(thumbnail_path)

    if output_path.exists() and output_path.stat().st_size > 0:
        logger.info("download.skip_existing", path=str(output_path))
        _move_sidecars()
        return output_path

    if output_path.exists() and output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)

    def _cleanup_temp() -> None:
        # Only remove obviously stale sidecar files. Keep partial downloads to allow resume.
        for p in output_path.parent.glob(output_path.stem + ".*"):
            if p == output_path:
                continue

            # Keep yt-dlp partial files to allow resume (-c).
            if p.suffix.endswith(".part"):
                continue

            # Keep info.json/thumbnail; we'll move them after download.
            if p.name.endswith(".info.json"):
                continue
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                continue

            p.unlink(missing_ok=True)

    _cleanup_temp()

    tmp_template = output_path.with_suffix(".%(ext)s")

    def _should_retry(exc: Exception) -> bool:
        return isinstance(exc, subprocess.CalledProcessError)

    def _do_download() -> None:
        args = [
            "yt-dlp",
            "--no-progress",
            "--no-playlist",
            "--retries",
            "3",
            "--fragment-retries",
            "3",
            # Resume partial downloads when possible.
            "-c",
            "--no-overwrites",
            "-f",
            # Prefer H.264/AVC (avc1) to avoid AV1 decode issues in some environments.
            # Keep mp4 where possible.
            "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format",
            "mp4",
            "-o",
            str(tmp_template),
        ]

        # Metadata sidecars (best-effort): info.json + thumbnail.
        if metadata_json_path is not None:
            args += ["--write-info-json"]
        if thumbnail_path is not None:
            args += ["--write-thumbnail", "--convert-thumbnails", "jpg"]

        args.append(youtube_url)

        run(args, logger=logger)

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

    _move_sidecars()

    logger.info("download.done", path=str(output_path), size_bytes=output_path.stat().st_size)
    return output_path
