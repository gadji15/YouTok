from __future__ import annotations

from video_worker.jobs import probe_video


def test_jobs_module_imports_probe_video() -> None:
    assert callable(probe_video)
