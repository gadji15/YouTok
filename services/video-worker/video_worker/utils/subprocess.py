from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

import structlog


def run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    logger: structlog.BoundLogger,
) -> None:
    logger.info("exec", args=list(args), cwd=str(cwd) if cwd else None)
    try:
        subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(
            "exec.failed",
            returncode=e.returncode,
            stdout=(e.stdout or "")[-4000:],
            stderr=(e.stderr or "")[-4000:],
        )
        raise
