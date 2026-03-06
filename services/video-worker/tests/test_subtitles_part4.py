from __future__ import annotations

import re
from pathlib import Path

from video_worker.pipeline.subtitles import write_word_level_ass_for_clip
from video_worker.pipeline.types import WordTiming


def _strip_ass_tags(s: str) -> str:
    return re.sub(r"\{[^}]*\}", "", s)


def test_word_level_karaoke_style_uses_yellow_highlight(tmp_path: Path) -> None:
    out = tmp_path / "subtitles.ass"

    words = [
        WordTiming(word="hello", start_seconds=0.0, end_seconds=0.5, confidence=1.0),
        WordTiming(word="world", start_seconds=0.5, end_seconds=1.0, confidence=1.0),
    ]

    write_word_level_ass_for_clip(
        clip_start_seconds=0.0,
        clip_end_seconds=2.0,
        words=words,
        output_path=out,
        template="modern_karaoke",
        placement=(2, 540, 1600),
    )

    text = out.read_text(encoding="utf-8")
    # Primary = white, Secondary = yellow (karaoke highlight)
    assert ",&H00FFFFFF,&H0000FFFF," in text


def test_word_level_ass_limits_words_per_line_to_six(tmp_path: Path) -> None:
    out = tmp_path / "subtitles.ass"

    # 12 words over ~6 seconds -> should stay in a single event, split across two lines.
    words = [
        WordTiming(word=f"w{i}", start_seconds=i * 0.5, end_seconds=(i + 1) * 0.5, confidence=1.0)
        for i in range(12)
    ]

    write_word_level_ass_for_clip(
        clip_start_seconds=0.0,
        clip_end_seconds=10.0,
        words=words,
        output_path=out,
        template="modern_karaoke",
        placement=(2, 540, 1600),
    )

    dialogue = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.startswith("Dialogue:")]
    assert len(dialogue) >= 1

    # Take the first event and analyze its text payload.
    payload = dialogue[0].split(",,", 1)[-1]
    payload = _strip_ass_tags(payload)

    assert "\\N" in payload
    lines = [p.strip() for p in payload.split("\\N") if p.strip()]
    assert lines

    for line in lines:
        tokens = [t for t in line.split() if t]
        assert len(tokens) <= 6
