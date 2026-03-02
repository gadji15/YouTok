from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration_seconds: float


def probe_video(path: Path) -> VideoInfo:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(proc.stdout)
    stream = payload["streams"][0]
    duration = float(payload["format"]["duration"])
    return VideoInfo(width=int(stream["width"]), height=int(stream["height"]), duration_seconds=duration)
