from __future__ import annotations

from video_worker.pipeline.segment import segment_candidates
from video_worker.pipeline.types import TranscriptSegment


def test_segment_candidates_produces_clips_within_bounds() -> None:
    segments = [
        TranscriptSegment(0.0, 5.0, "Today I'm going to show you a simple trick."),
        TranscriptSegment(5.0, 12.0, "What if you could do it twice as fast?"),
        TranscriptSegment(12.0, 25.0, "Most people make this mistake and never notice."),
        TranscriptSegment(25.0, 40.0, "Here's how to fix it quickly."),
        TranscriptSegment(40.0, 70.0, "And that's the whole thing."),
    ]

    clips = segment_candidates(segments=segments, min_seconds=15, max_seconds=60, max_clips=3)

    assert clips
    assert len(clips) <= 3
    for c in clips:
        assert 15 <= (c.end_seconds - c.start_seconds) <= 60
        assert c.clip_id.startswith("clip_")
        assert 0.0 <= c.score <= 1.0


def test_segment_candidates_prefers_hooky_text() -> None:
    segments = [
        TranscriptSegment(0.0, 20.0, "Monotone filler words."),
        TranscriptSegment(20.0, 40.0, "What if you never make this mistake again?"),
        TranscriptSegment(40.0, 65.0, "More filler."),
    ]

    clips = segment_candidates(segments=segments, min_seconds=15, max_seconds=60, max_clips=1)
    assert clips[0].start_seconds <= 20.0 <= clips[0].end_seconds
