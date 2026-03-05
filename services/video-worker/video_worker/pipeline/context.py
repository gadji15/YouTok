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
    storage_root: Path

    @property
    def project_dir(self) -> Path:
        return self.storage_root / "projects" / self.project_id

    @property
    def source_dir(self) -> Path:
        return self.project_dir / "source"

    @property
    def project_artifacts_dir(self) -> Path:
        return self.project_dir / "artifacts"

    @property
    def transcripts_dir(self) -> Path:
        return self.storage_root / "transcripts" / self.project_id

    @property
    def subtitles_dir(self) -> Path:
        return self.storage_root / "subtitles" / self.project_id

    @property
    def clips_dir(self) -> Path:
        return self.storage_root / "clips" / self.project_id

    @property
    def exports_dir(self) -> Path:
        return self.storage_root / "exports" / self.project_id

    def ensure_dirs(self) -> None:
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.project_artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        self.subtitles_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    @property
    def source_video_path(self) -> Path:
        return self.source_dir / "source.mp4"

    @property
    def audio_path(self) -> Path:
        return self.project_artifacts_dir / "audio.wav"

    @property
    def transcript_json_path(self) -> Path:
        return self.transcripts_dir / "transcript.json"

    @property
    def subtitles_srt_path(self) -> Path:
        return self.subtitles_dir / "subtitles.srt"

    @property
    def words_json_path(self) -> Path:
        return self.project_artifacts_dir / "words.json"

    @property
    def clips_json_path(self) -> Path:
        return self.project_artifacts_dir / "clips.json"

    @property
    def segments_json_path(self) -> Path:
        return self.project_artifacts_dir / "segments.json"

    @property
    def source_metadata_json_path(self) -> Path:
        return self.project_artifacts_dir / "source_metadata.json"

    @property
    def source_thumbnail_path(self) -> Path:
        return self.project_artifacts_dir / "thumbnail.jpg"
