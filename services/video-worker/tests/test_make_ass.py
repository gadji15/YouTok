from __future__ import annotations

from pathlib import Path

from video_worker.tools.make_ass import group_words_to_lines, write_ass


def test_group_words_to_lines_does_not_insert_space_before_punctuation() -> None:
    words = [
        {"word": "Bonjour", "start_seconds": 0.0, "end_seconds": 0.2},
        {"word": ",", "start_seconds": 0.2, "end_seconds": 0.25},
        {"word": "ça", "start_seconds": 0.25, "end_seconds": 0.4},
        {"word": "va", "start_seconds": 0.4, "end_seconds": 0.55},
        {"word": "?", "start_seconds": 0.55, "end_seconds": 0.6},
    ]

    lines = group_words_to_lines(words, max_chars=80)

    assert lines[0][0] == "Bonjour, ça va?"


def test_group_words_to_lines_end_time_is_last_included_word() -> None:
    words = [
        {"word": "one", "start_seconds": 0.0, "end_seconds": 0.4},
        {"word": "two", "start_seconds": 0.4, "end_seconds": 0.8},
        {"word": "three", "start_seconds": 0.8, "end_seconds": 1.2},
        {"word": "four", "start_seconds": 1.2, "end_seconds": 1.6},
    ]

    # Force a split before "three".
    lines = group_words_to_lines(words, max_chars=8)
    assert len(lines) >= 2

    first_text, first_start, first_end = lines[0]
    second_text, second_start, _ = lines[1]

    assert first_text == "one two"
    assert second_text.startswith("three")

    # Critical property: first event must not extend past the start of the next event.
    assert first_end <= second_start


def test_write_ass_does_not_escape_commas_and_wraps(tmp_path: Path) -> None:
    out = tmp_path / "test_make_ass.ass"

    lines = [("hello, world this is a very long line that should wrap", 0.0, 1.0)]

    write_ass(
        out=out,
        lines=lines,
        play_res_x=1080,
        play_res_y=1920,
        x=540,
        y=1400,
        an=2,
        template="modern",
        ui_safe_ymin=0.78,
    )

    text = out.read_text(encoding="utf-8")

    # Commas should not be escaped in dialogue text.
    assert "\\," not in text

    # Long lines should be wrapped using ASS line breaks.
    assert "\\N" in text
