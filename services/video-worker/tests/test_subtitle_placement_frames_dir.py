from __future__ import annotations

import subprocess

import structlog

from video_worker.pipeline.subtitle_placement import _extract_frames, choose_subtitle_placement


def test_extract_frames_does_not_crash_with_legacy_frames_dir(tmp_path, monkeypatch) -> None:
    work_dir = tmp_path / "subtitle_placement"
    legacy_frames = work_dir / "frames"
    legacy_frames.mkdir(parents=True)
    (legacy_frames / "frame_0001.jpg").write_text("old")

    def _fake_run(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    frames = _extract_frames(
        video_path=tmp_path / "source.mp4",
        start_seconds=0.0,
        end_seconds=1.0,
        work_dir=work_dir,
    )

    assert frames == []
    assert (legacy_frames / "frame_0001.jpg").exists()


def test_choose_subtitle_placement_does_not_crash_with_legacy_frames_dir(tmp_path, monkeypatch) -> None:
    work_dir = tmp_path / "subtitle_placement"
    legacy_frames = work_dir / "frames"
    (legacy_frames / "nested").mkdir(parents=True)
    (legacy_frames / "nested" / "old.txt").write_text("x")

    def _fake_run(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    placement = choose_subtitle_placement(
        source_video=tmp_path / "source.mp4",
        clip_start_seconds=0.0,
        clip_end_seconds=1.0,
        play_res_x=1080,
        play_res_y=1920,
        work_dir=work_dir,
        logger=structlog.get_logger(),
    )

    assert placement.alignment in {2, 8}
