from __future__ import annotations

import structlog

from video_worker.jobs import _ensure_title_candidates_for_clips
from video_worker.pipeline.types import ClipCandidate, TranscriptSegment


class _FakeTitleCandidate:
    def __init__(self, title: str):
        self.title = title


class _FakeTitleResult:
    def __init__(self, title: str):
        self.candidates = [_FakeTitleCandidate(title)]

    def to_payload(self) -> dict:
        return {
            "provider": "fake",
            "description": None,
            "hashtags": [],
            "candidates": [{"title": self.candidates[0].title, "score": 1.0, "features": {}}],
            "top3": [self.candidates[0].title],
        }


def test_titles_resume_uses_existing_candidates_without_regenerating() -> None:
    clips = [
        ClipCandidate("clip_001", 0.0, 10.0, 0.5, "baseline", title="T1"),
        ClipCandidate("clip_002", 10.0, 20.0, 0.6, "baseline", title="T2"),
    ]

    segments = [TranscriptSegment(0.0, 20.0, "hello world")]

    existing = {
        "clip_001": {"provider": "heuristic", "candidates": [], "top3": ["T1"]},
        "clip_002": {"provider": "heuristic", "candidates": [], "top3": ["T2"]},
    }

    def _should_not_be_called(**kwargs):
        raise AssertionError("generate_fn should not be called when existing candidates are complete")

    titles, updated = _ensure_title_candidates_for_clips(
        clips=clips,
        segments=segments,
        language="en",
        used_chapters=False,
        provider="heuristic",
        openai_api_key=None,
        openai_model="gpt-4o-mini",
        openai_base_url=None,
        logger=structlog.get_logger(),
        existing=existing,
        generate_fn=_should_not_be_called,
    )

    assert titles == existing
    assert [c.title for c in updated] == ["T1", "T2"]


def test_titles_resume_generates_missing_candidates_only() -> None:
    clips = [
        ClipCandidate("clip_001", 0.0, 10.0, 0.5, "baseline", title="T1"),
        ClipCandidate("clip_002", 10.0, 20.0, 0.6, "baseline", title="T2"),
    ]

    segments = [TranscriptSegment(0.0, 20.0, "hello world")]

    existing = {
        "clip_001": {"provider": "heuristic", "candidates": [], "top3": ["T1"]},
    }

    calls: list[str] = []

    def _generate_fn(*, clip, **kwargs):
        calls.append(clip.clip_id)
        return _FakeTitleResult(title=f"GEN_{clip.clip_id}")

    titles, updated = _ensure_title_candidates_for_clips(
        clips=clips,
        segments=segments,
        language="en",
        used_chapters=False,
        provider="heuristic",
        openai_api_key=None,
        openai_model="gpt-4o-mini",
        openai_base_url=None,
        logger=structlog.get_logger(),
        existing=existing,
        generate_fn=_generate_fn,
    )

    assert calls == ["clip_002"]
    assert "clip_001" in titles
    assert "clip_002" in titles
    assert [c.title for c in updated] == ["T1", "GEN_clip_002"]
