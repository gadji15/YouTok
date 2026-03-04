from __future__ import annotations

from video_worker.pipeline.subtitles import (
    write_srt,
    write_srt_for_clip,
    write_stylized_ass_for_clip,
    write_word_level_ass_for_clip,
)
from video_worker.pipeline.types import TranscriptSegment, WordTiming


def test_write_srt(tmp_path) -> None:
    out = tmp_path / "subtitles.srt"
    write_srt(
        segments=[
            TranscriptSegment(0.0, 1.23, "hello"),
            TranscriptSegment(2.0, 3.5, "world"),
        ],
        output_path=out,
    )

    text = out.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,230" in text
    assert "hello" in text


def test_write_srt_for_clip_is_relative(tmp_path) -> None:
    out = tmp_path / "clip.srt"
    write_srt_for_clip(
        clip_start_seconds=10.0,
        clip_end_seconds=20.0,
        segments=[
            TranscriptSegment(9.0, 11.0, "before"),
            TranscriptSegment(11.0, 12.0, "inside"),
            TranscriptSegment(20.0, 22.0, "after"),
        ],
        output_path=out,
    )

    text = out.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,000" in text
    assert "inside" in text
    assert "after" not in text


def test_write_ass_for_clip_is_relative(tmp_path) -> None:
    out = tmp_path / "subtitles.ass"
    write_stylized_ass_for_clip(
        clip_start_seconds=10.0,
        clip_end_seconds=20.0,
        segments=[
            TranscriptSegment(9.0, 11.0, "before"),
            TranscriptSegment(11.0, 12.0, "inside"),
            TranscriptSegment(20.0, 22.0, "after"),
        ],
        output_path=out,
    )

    text = out.read_text(encoding="utf-8")
    assert "PlayResX" in text
    # First included dialogue should start at 0 seconds relative.
    assert "Dialogue: 0,0:00:00.00" in text
    assert "inside" in text
    assert "after" not in text


def test_write_ass_karaoke_template(tmp_path) -> None:
    out = tmp_path / "subtitles_k.ass"
    write_stylized_ass_for_clip(
        clip_start_seconds=0.0,
        clip_end_seconds=2.0,
        segments=[TranscriptSegment(0.0, 2.0, "hello world")],
        output_path=out,
        template="karaoke",
    )

    text = out.read_text(encoding="utf-8")
    assert "\\k" in text
    assert "hello" in text and "world" in text


def test_write_word_level_ass_modern_is_not_karaoke_by_default(tmp_path) -> None:
    out = tmp_path / "subtitles_word.ass"

    words = [
        WordTiming(word="bonjour", start_seconds=0.0, end_seconds=0.5, confidence=1.0),
        WordTiming(word="hello", start_seconds=0.5, end_seconds=1.0, confidence=1.0),
        WordTiming(word="مرحبا", start_seconds=1.0, end_seconds=1.5, confidence=1.0),
    ]

    write_word_level_ass_for_clip(
        clip_start_seconds=0.0,
        clip_end_seconds=2.0,
        words=words,
        output_path=out,
        template="modern",
        placement=(2, 540, 1600),
    )

    text = out.read_text(encoding="utf-8")
    assert "Dialogue:" in text
    assert "\\pos(" in text
    assert "\\k" not in text


def test_write_word_level_ass_karaoke_contains_k_tags(tmp_path) -> None:
    out = tmp_path / "subtitles_word_k.ass"

    words = [
        WordTiming(word="hello", start_seconds=0.0, end_seconds=1.0, confidence=1.0),
        WordTiming(word="world", start_seconds=1.0, end_seconds=2.0, confidence=1.0),
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
    assert "\\k" in text


def test_write_word_level_ass_cinematic_karaoke_contains_cinematic_tags(tmp_path) -> None:
    out = tmp_path / "subtitles_word_cinematic.ass"

    words = [
        WordTiming(word="hello", start_seconds=0.0, end_seconds=1.0, confidence=1.0),
        WordTiming(word="world", start_seconds=1.0, end_seconds=2.0, confidence=1.0),
    ]

    write_word_level_ass_for_clip(
        clip_start_seconds=0.0,
        clip_end_seconds=2.0,
        words=words,
        output_path=out,
        template="cinematic_karaoke",
        placement=(2, 540, 1600),
    )

    text = out.read_text(encoding="utf-8")
    assert "\\fad(" in text
    assert "\\t(0,120" in text


def test_write_word_level_ass_splits_long_window_into_multiple_events(tmp_path) -> None:
    out = tmp_path / "subtitles_word_long.ass"

    # 30 words over 15 seconds.
    words = [
        WordTiming(word=f"w{i}", start_seconds=i * 0.5, end_seconds=(i + 1) * 0.5, confidence=1.0)
        for i in range(30)
    ]

    write_word_level_ass_for_clip(
        clip_start_seconds=0.0,
        clip_end_seconds=20.0,
        words=words,
        output_path=out,
        template="modern",
        placement=(2, 540, 1600),
    )

    text = out.read_text(encoding="utf-8")
    assert text.count("Dialogue:") >= 3
