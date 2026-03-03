from __future__ import annotations

import json
import re
from pathlib import Path

import structlog

from ..utils.files import atomic_write_text
from .types import TranscriptSegment, WordTiming


_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


def _auto_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass

    return "cpu"


def approximate_words_from_segments(*, segments: list[TranscriptSegment]) -> list[WordTiming]:
    words: list[WordTiming] = []

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        tokens = [m.group(0) for m in _WORD_RE.finditer(text)]
        if not tokens:
            tokens = [w for w in text.split() if w]
        if not tokens:
            continue

        start = float(seg.start_seconds)
        end = float(seg.end_seconds)
        dur = max(0.01, end - start)

        step = dur / len(tokens)
        for idx, w in enumerate(tokens):
            w_start = start + idx * step
            w_end = start + (idx + 1) * step
            words.append(
                WordTiming(
                    word=w,
                    start_seconds=float(w_start),
                    end_seconds=float(w_end),
                    confidence=None,
                )
            )

    return words


def align_words_with_whisperx(
    *,
    audio_path: Path,
    segments: list[TranscriptSegment],
    language: str | None,
    logger: structlog.BoundLogger,
    device: str = "auto",
) -> list[WordTiming] | None:
    """Best-effort WhisperX forced alignment.

    Returns None when WhisperX isn't installed or alignment fails.
    """

    try:
        import whisperx
    except Exception:
        logger.info("align.whisperx_unavailable")
        return None

    chosen_device = _auto_device() if device == "auto" else device

    try:
        audio = whisperx.load_audio(str(audio_path))

        lang = (language or "en").lower().strip()
        model_a, metadata = whisperx.load_align_model(language_code=lang, device=chosen_device)

        whisperx_segments = [
            {"start": s.start_seconds, "end": s.end_seconds, "text": s.text}
            for s in segments
            if s.text.strip()
        ]

        aligned = whisperx.align(
            whisperx_segments,
            model_a,
            metadata,
            audio,
            chosen_device,
            return_char_alignments=False,
        )

        out: list[WordTiming] = []
        for seg in aligned.get("segments", []) or []:
            for w in seg.get("words", []) or []:
                word = (w.get("word") or "").strip()
                if not word:
                    continue

                start = w.get("start")
                end = w.get("end")
                if start is None or end is None:
                    continue

                out.append(
                    WordTiming(
                        word=word,
                        start_seconds=float(start),
                        end_seconds=float(end),
                        confidence=float(w.get("score")) if w.get("score") is not None else None,
                    )
                )

        if not out:
            return None

        out.sort(key=lambda x: (x.start_seconds, x.end_seconds))
        logger.info("align.whisperx_done", word_count=len(out), device=chosen_device)
        return out
    except Exception:
        logger.exception("align.whisperx_failed", device=chosen_device)
        return None


def write_words_json(*, words: list[WordTiming], output_path: Path) -> None:
    payload = {
        "words": [
            {
                "word": w.word,
                "start": w.start_seconds,
                "end": w.end_seconds,
                "confidence": w.confidence,
            }
            for w in words
        ]
    }

    atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2))


def load_words_json(path: Path) -> list[WordTiming]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: list[WordTiming] = []
    for w in raw.get("words", []) or []:
        if not isinstance(w, dict):
            continue
        word = str(w.get("word") or "").strip()
        if not word:
            continue
        start = w.get("start")
        end = w.get("end")
        if start is None or end is None:
            continue
        out.append(
            WordTiming(
                word=word,
                start_seconds=float(start),
                end_seconds=float(end),
                confidence=float(w.get("confidence")) if w.get("confidence") is not None else None,
            )
        )
    out.sort(key=lambda x: (x.start_seconds, x.end_seconds))
    return out
