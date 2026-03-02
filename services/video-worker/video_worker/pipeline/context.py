from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JobContext:
    job_id: str
    project_id: str
    youtube_url: str
    callback_url: str
    callback_secret: str
    root_dir: Path

    @property
    def source_dir(self) -> Path:
        return self.root_dir / "source"

    @property
    def artifacts_dir(self) -> Path:
        return self.root_dir / "artifacts"

    @property
    def clips_dir(self) -> Path:
        return self.root_dir / "clips"

    def ensure_dirs(self) -> None:
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    @property
    def source_video_path(self) -> Path:
        return self.source_dir / "source.mp4"

    @property
    def audio_path(self) -> Path:
        return self.artifacts_dir / "audio.wav"

    @property
    def transcript_json_path(self) -> Path:
        return self.artifacts_dir / "transcript.json"

    @property
    def subtitles_srt_path(self) -> Path:
        return self.artifacts_dir / "subtitles.srt"

    @property
    def clips_json_path(self) -> Path:
        return self.artifacts_dir / "clips.json"
