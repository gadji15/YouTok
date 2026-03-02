from __future__ import annotations

from video_worker.pipeline.title_generator import generate_title_candidates_for_clip
from video_worker.pipeline.types import ClipCandidate, TranscriptSegment


def test_generate_title_candidates_heuristic_produces_top3_and_max_len() -> None:
    segs = [
        TranscriptSegment(0.0, 10.0, "Most people make this mistake."),
        TranscriptSegment(10.0, 20.0, "What if you could fix it in 1 minute?"),
    ]

    clip = ClipCandidate(
        clip_id="clip_001",
        start_seconds=0.0,
        end_seconds=20.0,
        score=0.8,
        reason="question_hook,pattern_interrupt",
    )

    res = generate_title_candidates_for_clip(
        clip=clip,
        segments=segs,
        language="en",
        provider="heuristic",
        logger=__import__("structlog").get_logger(),
    )

    assert res.provider == "heuristic"
    assert res.candidates
    assert len(res.top3) <= 3

    for c in res.candidates:
        assert len(c.title) <= 60
        assert 0.0 <= c.score <= 1.0
