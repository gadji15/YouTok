from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_worker.pipeline.word_alignment import write_words_json
from video_worker.pipeline.types import TranscriptSegment


def main() -> None:
    parser = argparse.ArgumentParser(description="WhisperX forced alignment: wav -> words.json")
    parser.add_argument("audio", type=Path, help="Path to .wav/.mp3/.m4a audio")
    parser.add_argument("--language", default="en", help="Language code (e.g. en, fr)")
    parser.add_argument("--device", default="auto", help="auto|cpu|cuda|mps")
    parser.add_argument("--whisper-model", default="base", help="Whisper model name for WhisperX (e.g. base, small)")
    parser.add_argument("--output", type=Path, default=Path("words.json"), help="Output JSON path")
    parser.add_argument(
        "--segments-json",
        type=Path,
        default=None,
        help="Optional transcript.json (with segments). If not provided, WhisperX will transcribe first.",
    )

    args = parser.parse_args()

    try:
        import whisperx
    except Exception as e:
        raise SystemExit(
            "whisperx is not installed. Install it with: pip install -r requirements-align.txt\n"
            f"Import error: {e}"
        )

    audio = whisperx.load_audio(str(args.audio))

    if args.segments_json:
        raw = json.loads(args.segments_json.read_text(encoding="utf-8"))
        segments = [
            TranscriptSegment(
                start_seconds=float(s.get("start")),
                end_seconds=float(s.get("end")),
                text=str(s.get("text") or "").strip(),
            )
            for s in raw.get("segments", [])
            if isinstance(s, dict) and str(s.get("text") or "").strip()
        ]

        whisperx_segments = [
            {"start": s.start_seconds, "end": s.end_seconds, "text": s.text} for s in segments
        ]
    else:
        model = whisperx.load_model(args.whisper_model, args.device)
        res = model.transcribe(audio)
        whisperx_segments = res["segments"]

    model_a, metadata = whisperx.load_align_model(language_code=args.language, device=args.device)
    aligned = whisperx.align(
        whisperx_segments,
        model_a,
        metadata,
        audio,
        args.device,
        return_char_alignments=False,
    )

    words = []
    for seg in aligned.get("segments", []) or []:
        for w in seg.get("words", []) or []:
            word = (w.get("word") or "").strip()
            if not word:
                continue
            if w.get("start") is None or w.get("end") is None:
                continue
            words.append(
                {
                    "word": word,
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                    "confidence": float(w.get("score")) if w.get("score") is not None else None,
                }
            )

    # Reuse our writer to keep format identical to pipeline.
    from video_worker.pipeline.types import WordTiming

    write_words_json(
        words=[
            WordTiming(
                word=w["word"],
                start_seconds=w["start"],
                end_seconds=w["end"],
                confidence=w.get("confidence"),
            )
            for w in words
        ],
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
