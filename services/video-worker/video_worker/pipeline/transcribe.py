from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog

from ..utils.files import atomic_write_text
from .types import TranscriptSegment


def _auto_device() -> str:
    """Best-effort device selection.

    - cuda if available
    - mps on Apple Silicon if available
    - otherwise cpu

    If torch isn't installed, falls back to cpu.
    """

    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass

    return "cpu"


@lru_cache(maxsize=4)
def _load_whisper_model(model_name: str, device: str):
    import whisper

    return whisper.load_model(model_name, device=device)


def transcribe_audio(
    *,
    audio_path: Path,
    model_name: str,
    logger: structlog.BoundLogger,
    device: str = "auto",
    temperature: float = 0.0,
    beam_size: int = 1,
    best_of: int = 1,
) -> list[TranscriptSegment]:
    chosen_device = _auto_device() if device == "auto" else device

    logger.info(
        "transcribe.start",
        model=model_name,
        audio_path=str(audio_path),
        device=chosen_device,
        temperature=temperature,
        beam_size=beam_size,
        best_of=best_of,
    )

    def _do_transcribe(chosen: str) -> dict[str, Any]:
        model = _load_whisper_model(model_name, chosen)
        fp16 = chosen == "cuda"
        return model.transcribe(
            str(audio_path),
            fp16=fp16,
            temperature=float(temperature),
            beam_size=max(1, int(beam_size)),
            best_of=max(1, int(best_of)),
        )

    try:
        result = _do_transcribe(chosen_device)
    except Exception:
        # GPU path can fail (missing drivers, OOM, etc.). Fall back to CPU.
        if chosen_device != "cpu":
            logger.exception("transcribe.device_failed_fallback_cpu", device=chosen_device)
            result = _do_transcribe("cpu")
        else:
            raise

    segments: list[TranscriptSegment] = []
    for seg in result.get("segments", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start_seconds=float(seg["start"]),
                end_seconds=float(seg["end"]),
                text=text,
            )
        )

    logger.info("transcribe.done", segment_count=len(segments), device=chosen_device)
    return segments


def write_transcript_json(*, segments: list[TranscriptSegment], output_path: Path) -> None:
    payload = {
        "segments": [
            {
                "start": s.start_seconds,
                "end": s.end_seconds,
                "text": s.text,
            }
            for s in segments
        ]
    }
    atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2))
