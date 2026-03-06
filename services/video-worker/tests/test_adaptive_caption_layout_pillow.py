from __future__ import annotations

import re
from pathlib import Path

import pytest

from video_worker.pipeline.subtitles import write_word_level_ass_for_clip
from video_worker.pipeline.types import WordTiming
from video_worker.utils.text_measure import measure_text_width_px, resolve_font_path, strip_ass_tags


def _safe_width_px(*, play_res_x: int) -> int:
    return int(play_res_x) - 2 * int(round(72 * float(play_res_x) / 1080.0))


def _extract_payload(dialogue_line: str) -> str:
    return dialogue_line.split(",,", 1)[-1]


def _extract_override_font_size(payload: str) -> int:
    m = re.search(r"\\fs(\d+)", payload)
    assert m is not None
    return int(m.group(1))


def test_word_level_ass_shrinks_font_and_stays_within_safe_width(tmp_path: Path) -> None:
    font_path = resolve_font_path()
    if font_path is None:
        pytest.skip("no font available for deterministic width measurement")

    out = tmp_path / "subtitles.ass"

    words = [
        WordTiming(word="WWWWWW", start_seconds=i * 0.35, end_seconds=(i + 1) * 0.35, confidence=1.0)
        for i in range(6)
    ]

    write_word_level_ass_for_clip(
        clip_start_seconds=0.0,
        clip_end_seconds=5.0,
        words=words,
        output_path=out,
        template="modern_karaoke",
        placement=(2, 540, 1600),
        max_words_per_line=3,
    )

    text = out.read_text(encoding="utf-8")

    m_style = re.search(r"Style: Default,Noto Sans,(\d+),", text)
    assert m_style is not None
    style_font_size = int(m_style.group(1))

    dialogue = [ln for ln in text.splitlines() if ln.startswith("Dialogue:")]
    assert dialogue

    safe_width = _safe_width_px(play_res_x=1080)

    first_payload = _extract_payload(dialogue[0])
    event_font_size = _extract_override_font_size(first_payload)

    # The line is intentionally wide; we expect adaptive shrinking to kick in.
    assert event_font_size <= style_font_size

    for ln in dialogue:
        payload = _extract_payload(ln)
        font_px = _extract_override_font_size(payload)

        plain = strip_ass_tags(payload)
        for line in [p for p in plain.split("\\N") if p.strip()]:
            width = measure_text_width_px(text=line.strip(), font_path=font_path, font_size=font_px)
            assert width <= safe_width


def test_word_level_ass_splits_overwide_tokens_to_prevent_overflow(tmp_path: Path) -> None:
    font_path = resolve_font_path()
    if font_path is None:
        pytest.skip("no font available for deterministic width measurement")

    out = tmp_path / "subtitles.ass"

    # A single unbreakable token would normally overflow.
    long_word = "W" * 250

    words = [
        WordTiming(word=long_word, start_seconds=0.0, end_seconds=1.0, confidence=1.0),
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
    dialogue = [ln for ln in text.splitlines() if ln.startswith("Dialogue:")]
    assert dialogue

    safe_width = _safe_width_px(play_res_x=1080)

    for ln in dialogue:
        payload = _extract_payload(ln)
        font_px = _extract_override_font_size(payload)

        plain = strip_ass_tags(payload)
        for line in [p for p in plain.split("\\N") if p.strip()]:
            width = measure_text_width_px(text=line.strip(), font_path=font_path, font_size=font_px)
            assert width <= safe_width
