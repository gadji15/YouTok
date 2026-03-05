from __future__ import annotations

import json
import math
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
    language: str | None = None,
    initial_prompt: str | None = None,
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
        language=language,
        has_initial_prompt=bool(initial_prompt and initial_prompt.strip()),
        temperature=temperature,
        beam_size=beam_size,
        best_of=best_of,
    )

    def _do_transcribe(chosen: str) -> dict[str, Any]:
        model = _load_whisper_model(model_name, chosen)
        fp16 = chosen == "cuda"

        prompt = (initial_prompt or "").strip()
        lang = (language or "").strip().lower() or None

        return model.transcribe(
            str(audio_path),
            fp16=fp16,
            task="transcribe",
            language=lang,
            initial_prompt=(prompt if prompt else None),
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

    detected_language = result.get("language")

    segments: list[TranscriptSegment] = []
    for seg in result.get("segments", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue

        # Whisper provides avg_logprob (log probability per token). Convert to a
        # rough 0..1 confidence signal.
        avg_logprob = seg.get("avg_logprob")
        confidence = None
        if isinstance(avg_logprob, (int, float)):
            try:
                confidence = float(max(0.0, min(1.0, math.exp(float(avg_logprob)))))
            except (OverflowError, ValueError, TypeError):
                confidence = None

        segments.append(
            TranscriptSegment(
                start_seconds=float(seg["start"]),
                end_seconds=float(seg["end"]),
                text=text,
                confidence=confidence,
            )
        )

    logger.info(
        "transcribe.done",
        segment_count=len(segments),
        device=chosen_device,
        detected_language=detected_language,
    )
    return segments


def write_transcript_json(
    *,
    segments: list[TranscriptSegment],
    output_path: Path,
    meta: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "segments": [
            {
                "start": s.start_seconds,
                "end": s.end_seconds,
                "text": s.text,
                "confidence": s.confidence,
            }
            for s in segments
        ]
    }

    if meta:
        payload["meta"] = meta

    atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2))
