from __future__ import annotations

import array
import math
import wave

from video_worker.pipeline.segment import segment_candidates
from video_worker.pipeline.types import TranscriptSegment


def _write_test_wav(path) -> None:
    sr = 16000
    samples: list[int] = []

    # 1s silence
    samples.extend([0] * sr)

    # 4s tone
    freq = 440.0
    amp = 0.2
    for i in range(4 * sr):
        v = int(amp * 32767.0 * math.sin(2.0 * math.pi * freq * (i / sr)))
        samples.append(v)

    # 1s silence
    samples.extend([0] * sr)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(array.array("h", samples).tobytes())


def test_segment_candidates_polishes_silence_boundaries(tmp_path) -> None:
    wav_path = tmp_path / "audio.wav"
    _write_test_wav(wav_path)

    segments = [
        TranscriptSegment(0.0, 6.0, "What if you never make this mistake again?")
    ]

    clips = segment_candidates(
        segments=segments,
        min_seconds=2,
        max_seconds=6,
        max_clips=1,
        audio_path=wav_path,
    )

    assert clips
    c = clips[0]

    # Expect leading/trailing silence to be trimmed.
    assert c.start_seconds > 0.4
    assert c.end_seconds < 5.7
    assert (c.end_seconds - c.start_seconds) >= 2.0
