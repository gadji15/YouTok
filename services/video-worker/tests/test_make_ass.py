from __future__ import annotations

from video_worker.tools.make_ass import group_words_to_lines


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
