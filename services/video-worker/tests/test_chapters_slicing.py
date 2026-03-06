from __future__ import annotations

from video_worker.pipeline.chapters import YoutubeChapter, build_chapter_clips, build_sequential_clips
from video_worker.pipeline.types import TranscriptSegment


def test_build_sequential_clips_merges_small_tail() -> None:
    clips = build_sequential_clips(duration_seconds=370.0, max_seconds=180.0, min_seconds=60.0)

    assert [(c.start_seconds, c.end_seconds) for c in clips] == [
        (0.0, 180.0),
        (180.0, 370.0),
    ]


def test_build_sequential_clips_keeps_tail_when_big_enough() -> None:
    clips = build_sequential_clips(duration_seconds=430.0, max_seconds=180.0, min_seconds=60.0)

    assert [(c.start_seconds, c.end_seconds) for c in clips] == [
        (0.0, 180.0),
        (180.0, 360.0),
        (360.0, 430.0),
    ]


def test_build_chapter_clips_merges_small_tail_within_chapter() -> None:
    chapters = [YoutubeChapter(title="Ch1", start_seconds=0.0, end_seconds=370.0)]

    # Provide minimal transcript segments (ordering matters for _collect_text).
    segments = [
        TranscriptSegment(start_seconds=0.0, end_seconds=370.0, text="hello", confidence=None),
    ]

    clips = build_chapter_clips(chapters=chapters, segments=segments, max_seconds=180.0, min_seconds=60.0)

    assert [(c.start_seconds, c.end_seconds) for c in clips] == [
        (0.0, 180.0),
        (180.0, 370.0),
    ]
    assert clips[0].title == "Ch1 (Part 1)"
    assert clips[1].title == "Ch1 (Part 2)"
