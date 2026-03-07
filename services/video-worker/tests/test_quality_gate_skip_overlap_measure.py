from __future__ import annotations

from pathlib import Path

import structlog

from video_worker.pipeline.clip import render_clips
from video_worker.pipeline.subtitle_placement import SubtitlePlacement
from video_worker.pipeline.types import ClipCandidate, TranscriptSegment, WordTiming
from video_worker.utils.ffprobe import VideoInfo


def _patch_minimal_render(monkeypatch, *, tmp_path: Path) -> tuple[Path, Path]:
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"fake")

    output_dir = tmp_path / "clips"

    monkeypatch.setattr(
        "video_worker.pipeline.clip.probe_video",
        lambda _path: VideoInfo(width=1920, height=1080, duration_seconds=120.0),
    )

    def fake_write_srt_for_clip(*, output_path: Path, **kwargs) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")

    monkeypatch.setattr("video_worker.pipeline.clip.write_srt_for_clip", fake_write_srt_for_clip)

    monkeypatch.setattr(
        "video_worker.pipeline.clip.choose_subtitle_placement",
        lambda **kwargs: SubtitlePlacement(alignment=2, x=540, y=1600),
    )

    def fake_write_word_level_ass_for_clip(*, output_path: Path, **kwargs) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("[Script Info]\nTitle: test\n", encoding="utf-8")

    monkeypatch.setattr("video_worker.pipeline.clip.write_word_level_ass_for_clip", fake_write_word_level_ass_for_clip)

    def fake_run(args, *, logger=None, heartbeat_callback=None, heartbeat_interval_seconds=60.0, line_callback=None, cancel_check=None):
        out_video = Path(args[-1])
        out_video.parent.mkdir(parents=True, exist_ok=True)
        out_video.write_bytes(b"fake-mp4")

    monkeypatch.setattr("video_worker.pipeline.clip.run", fake_run)

    return source_video, output_dir


def test_render_skips_overlap_measurement_when_quality_gate_disabled(monkeypatch, tmp_path) -> None:
    source_video, output_dir = _patch_minimal_render(monkeypatch, tmp_path=tmp_path)

    def boom(*args, **kwargs):
        raise AssertionError("measure_overlap_p95_for_video should not be called")

    monkeypatch.setattr("video_worker.pipeline.clip.measure_overlap_p95_for_video", boom)

    clips = [ClipCandidate(clip_id="clip_001", start_seconds=0.0, end_seconds=5.0, score=0.5, reason="test")]
    transcript = [TranscriptSegment(start_seconds=0.0, end_seconds=1.0, text="Hi", confidence=1.0)]
    words = [WordTiming(word="Hi", start_seconds=0.0, end_seconds=0.5, confidence=1.0)]

    rendered = render_clips(
        source_video=source_video,
        transcript_segments=transcript,
        clips=clips,
        output_dir=output_dir,
        logger=structlog.get_logger(),
        subtitles_enabled=True,
        subtitle_template="default",
        output_aspect="source",
        stabilization_enabled=False,
        visual_enhance_enabled=False,
        word_timings=words,
        quality_gate_enabled=False,
    )

    assert rendered and rendered[0]["clip_id"] == "clip_001"


def test_render_measures_overlap_when_quality_gate_enabled(monkeypatch, tmp_path) -> None:
    source_video, output_dir = _patch_minimal_render(monkeypatch, tmp_path=tmp_path)

    seen = {"called": 0}

    def fake_measure(*args, **kwargs):
        seen["called"] += 1
        return 0.0, 0.0

    monkeypatch.setattr("video_worker.pipeline.clip.measure_overlap_p95_for_video", fake_measure)

    clips = [ClipCandidate(clip_id="clip_001", start_seconds=0.0, end_seconds=5.0, score=0.5, reason="test")]
    transcript = [TranscriptSegment(start_seconds=0.0, end_seconds=1.0, text="Hi", confidence=1.0)]
    words = [WordTiming(word="Hi", start_seconds=0.0, end_seconds=0.5, confidence=1.0)]

    render_clips(
        source_video=source_video,
        transcript_segments=transcript,
        clips=clips,
        output_dir=output_dir,
        logger=structlog.get_logger(),
        subtitles_enabled=True,
        subtitle_template="default",
        output_aspect="source",
        stabilization_enabled=False,
        visual_enhance_enabled=False,
        word_timings=words,
        quality_gate_enabled=True,
        quality_gate_max_attempts=1,
    )

    assert seen["called"] == 1
