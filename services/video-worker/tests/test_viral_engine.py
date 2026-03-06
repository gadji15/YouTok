from __future__ import annotations

from pathlib import Path

from video_worker.pipeline.types import TranscriptSegment, WordTiming
from video_worker.pipeline.viral_engine import detect_hook_start_seconds, write_viral_overlays_ass_for_clip


def test_detect_hook_start_seconds_prefers_earliest_strong_hook() -> None:
    segments = [
        TranscriptSegment(0.0, 1.0, "um so"),
        TranscriptSegment(1.0, 2.0, "Wait. Here's the secret."),
        TranscriptSegment(2.0, 6.0, "More context."),
    ]

    hook = detect_hook_start_seconds(
        segments=segments,
        words=None,
        audio_path=None,
        clip_start_seconds=0.0,
        clip_end_seconds=6.0,
        language="en",
        hook_window_seconds=3.0,
        shift_max_seconds=2.0,
    )

    assert hook is not None
    assert abs(hook.start_seconds - 1.0) < 0.4
    assert hook.score >= 0.62


def test_write_viral_overlays_ass_for_clip_writes_hook_and_emojis(tmp_path: Path) -> None:
    segments = [
        TranscriptSegment(0.0, 2.0, "Wait. Here's the secret."),
        TranscriptSegment(2.0, 4.0, "And it's free."),
    ]

    words = [
        WordTiming("wait", 0.05, 0.20),
        WordTiming("secret", 0.80, 1.00),
        WordTiming("free", 2.40, 2.60),
    ]

    out = tmp_path / "viral_overlays.ass"

    write_viral_overlays_ass_for_clip(
        clip_start_seconds=0.0,
        clip_end_seconds=4.0,
        transcript_segments=segments,
        word_timings=words,
        language="en",
        output_path=out,
        play_res_x=1080,
        play_res_y=1920,
        hook_text_enabled=True,
        emojis_enabled=True,
        max_emojis=6,
    )

    raw = out.read_text(encoding="utf-8")
    assert "Style: Hook" in raw
    assert "Dialogue:" in raw
    assert "secret" in raw.lower()
    assert "🤫" in raw
    assert "🎁" in raw
