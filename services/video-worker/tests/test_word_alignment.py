from __future__ import annotations

from video_worker.pipeline.types import TranscriptSegment
from video_worker.pipeline.word_alignment import approximate_words_from_segments, load_words_json, write_words_json


def test_approximate_words_from_segments_produces_monotonic_words() -> None:
    words = approximate_words_from_segments(
        segments=[TranscriptSegment(1.0, 3.0, "hello world")]
    )

    assert [w.word for w in words] == ["hello", "world"]
    assert words[0].start_seconds >= 1.0
    assert words[0].end_seconds <= words[1].start_seconds
    assert words[-1].end_seconds <= 3.0


def test_write_and_load_words_json_roundtrip(tmp_path) -> None:
    out = tmp_path / "words.json"

    words = approximate_words_from_segments(
        segments=[TranscriptSegment(0.0, 1.0, "one two")]
    )

    write_words_json(words=words, output_path=out)
    loaded = load_words_json(out)

    assert [w.word for w in loaded] == ["one", "two"]
    assert loaded[0].start_seconds == words[0].start_seconds
