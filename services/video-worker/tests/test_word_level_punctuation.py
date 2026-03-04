from __future__ import annotations

from pathlib import Path

from video_worker.pipeline.subtitles import write_word_level_ass_for_clip
from video_worker.pipeline.types import WordTiming


def test_word_level_ass_merges_punctuation_tokens(tmp_path: Path) -> None:
    out = tmp_path / "out.ass"

    words = [
        WordTiming(word="Bonjour", start_seconds=0.0, end_seconds=0.2, confidence=1.0),
        WordTiming(word=",", start_seconds=0.2, end_seconds=0.25, confidence=1.0),
        WordTiming(word="ça", start_seconds=0.25, end_seconds=0.4, confidence=1.0),
        WordTiming(word="va", start_seconds=0.4, end_seconds=0.55, confidence=1.0),
        WordTiming(word="?", start_seconds=0.55, end_seconds=0.6, confidence=1.0),
    ]

    write_word_level_ass_for_clip(
        clip_start_seconds=0.0,
        clip_end_seconds=1.0,
        words=words,
        output_path=out,
        placement=(2, 540, 1400),
        template="modern_karaoke",
    )

    text = out.read_text(encoding="utf-8")
    assert "Bonjour," in text
    assert "va?" in text
    assert "Bonjour ," not in text
    assert "va ?" not in text
