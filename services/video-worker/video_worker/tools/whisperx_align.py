#!/usr/bin/env python3
"""whisperx_align.py

CLI helper: transcribe a WAV with Whisper (GPU if available) and run WhisperX
forced-alignment when available. Produces a words.json list with entries:
  {"word": "...", "start_seconds": 1.23, "end_seconds": 1.56, "confidence": 0.98}

This script is intentionally defensive: if whisperx is not installed it falls
back to a conservative, proportional split of segments into words.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict


logger = logging.getLogger("whisperx_align")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def try_whisper_transcribe(wav_path: Path, model_name: str = "base", device: str = "cpu"):
    try:
        import whisper

        logger.info("loading whisper model %s on %s", model_name, device)
        m = whisper.load_model(model_name, device=device)
        logger.info("transcribing (whisper)")
        r = m.transcribe(str(wav_path))
        # r['segments'] typically each has {start,end,text}
        return r
    except Exception as e:
        logger.warning("whisper transcribe failed: %s", e)
        return None


def try_whisperx_align(wav_path: Path, transcribe_result) -> List[Dict]:
    try:
        import whisperx

        logger.info("running whisperx alignment")
        device = "cuda" if whisperx.is_available() and "cuda" in whisperx.available_devices() else "cpu"
        # whisperx.align_segments expects model output & audio
        model_a, metadata = whisperx.load_align_model(device=device)
        aligned = whisperx.align(transcribe_result["segments"], str(wav_path), model_a, metadata, device=device)
        # aligned contains 'word_segments' typically
        words = []
        for w in aligned.get("word_segments", []) or aligned.get("words", []):
            words.append({
                "word": w.get("word") or w.get("text"),
                "start_seconds": float(w.get("start", 0.0)),
                "end_seconds": float(w.get("end", 0.0)),
                "confidence": float(w.get("confidence", 1.0)),
            })
        return words
    except Exception as e:
        logger.warning("whisperx align failed or not available: %s", e)
        return []


def fallback_proportional_split(transcribe_result) -> List[Dict]:
    logger.info("falling back to proportional split of segments into words")
    words: List[Dict] = []
    for seg in transcribe_result.get("segments", []):
        text = seg.get("text", "").strip()
        if not text:
            continue
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start + 0.01))
        tokens = [t for t in text.split() if t]
        if not tokens:
            continue
        dur = max(0.01, end - start)
        per = dur / len(tokens)
        for i, t in enumerate(tokens):
            s = start + i * per
            e = s + per
            words.append({"word": t, "start_seconds": s, "end_seconds": e, "confidence": 1.0})
    return words


def main(argv=None):
    p = argparse.ArgumentParser(description="Whisper + WhisperX align helper")
    p.add_argument("--wav", required=True, type=Path, help="Input WAV file")
    p.add_argument("--out", required=True, type=Path, help="Output words.json")
    p.add_argument("--model", default="base", help="Whisper model name")
    p.add_argument("--device", default="cpu", help="cuda or cpu")
    args = p.parse_args(argv)

    wav = args.wav
    out = args.out

    if not wav.exists():
        logger.error("wav not found: %s", wav)
        sys.exit(2)

    tr = try_whisper_transcribe(wav, model_name=args.model, device=args.device)
    if tr is None:
        logger.error("transcription failed"); sys.exit(2)

    words = try_whisperx_align(wav, tr) or fallback_proportional_split(tr)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("wrote %d words to %s", len(words), out)


if __name__ == "__main__":
    main()
