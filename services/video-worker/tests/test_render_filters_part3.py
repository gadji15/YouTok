from __future__ import annotations

from pathlib import Path

import structlog

from video_worker.pipeline.clip import render_clips
from video_worker.pipeline.types import ClipCandidate, TranscriptSegment


def test_render_clips_builds_filters_for_stabilization_and_visual_enhance(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(args, logger=None):
        calls.append([str(a) for a in args])

        # Simulate vidstabdetect output.
        if args and args[0] == "ffmpeg" and "vidstabdetect" in " ".join([str(a) for a in args]):
            vf = args[args.index("-vf") + 1]
            if "result=" in vf:
                trf = vf.split("result=", 1)[1]
                trf = trf.replace("\\\\", "\\").replace("\\:", ":").replace("\\,", ",")
                Path(trf).parent.mkdir(parents=True, exist_ok=True)
                Path(trf).write_text("stub\n", encoding="utf-8")
            return

        # Create output file for the final ffmpeg render command.
        if args and args[0] == "ffmpeg" and str(args[-1]).endswith("video.mp4"):
            Path(args[-1]).parent.mkdir(parents=True, exist_ok=True)
            Path(args[-1]).write_bytes(b"x")

    monkeypatch.setattr("video_worker.pipeline.clip.run", fake_run)
    monkeypatch.setattr(
        "video_worker.pipeline.clip.probe_video",
        lambda *_args, **_kwargs: type("V", (), {"width": 1920, "height": 1080})(),
    )
    monkeypatch.setattr("video_worker.pipeline.clip.estimate_face_center_x", lambda **_kwargs: 0.5)

    clips = [ClipCandidate("clip_001", 0.0, 5.0, 0.9, "baseline")]
    segs = [TranscriptSegment(0.0, 5.0, "hello")]

    out = render_clips(
        source_video=tmp_path / "src.mp4",
        transcript_segments=segs,
        clips=[
            ClipCandidate(
                "clip_001",
                0.0,
                5.0,
                0.9,
                "baseline",
                features={"hook_score": 0.9},
            )
        ],
        output_dir=tmp_path / "out",
        logger=structlog.get_logger(),
        subtitles_enabled=False,
        output_aspect="vertical",
        stabilization_enabled=True,
        visual_enhance_enabled=True,
        viral_engine_enabled=True,
        viral_zoom_intensity=0.06,
        viral_hook_text_enabled=False,
        viral_emojis_enabled=False,
    )

    assert out and out[0]["clip_id"] == "clip_001"

    ffmpeg_cmds = [c for c in calls if c and c[0] == "ffmpeg" and c[-1].endswith("video.mp4")]
    assert len(ffmpeg_cmds) == 1

    cmd = ffmpeg_cmds[0]
    vf = cmd[cmd.index("-vf") + 1]

    assert ("vidstabtransform=" in vf) or ("deshake=" in vf)
    assert "eq=contrast=" in vf
    assert "unsharp=" in vf
    assert "crop=w='iw/(if(between(t\\,0\\," in vf

    assert cmd[cmd.index("-maxrate") + 1] == "10M"
    assert cmd[cmd.index("-bufsize") + 1] == "12M"
