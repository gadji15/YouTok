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
    heartbeat_callback=None,
    heartbeat_interval_seconds: float = 60.0,
) -> None:
    logger.info("exec", args=list(args), cwd=str(cwd) if cwd else None)

    if heartbeat_callback is None:
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
        return

    import time
    from collections import deque
    from threading import Thread

    stdout_tail: deque[str] = deque(maxlen=2000)
    stderr_tail: deque[str] = deque(maxlen=2000)

    def _drain(stream, buf: deque[str]) -> None:
        try:
            for line in iter(stream.readline, ""):
                if not line:
                    break
                buf.append(line)
        finally:
            try:
                stream.close()
            except Exception:
                pass

    proc = subprocess.Popen(
        list(args),
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    assert proc.stdout is not None
    assert proc.stderr is not None

    t_out = Thread(target=_drain, args=(proc.stdout, stdout_tail), daemon=True)
    t_err = Thread(target=_drain, args=(proc.stderr, stderr_tail), daemon=True)
    t_out.start()
    t_err.start()

    started = time.time()
    last_beat = started

    while True:
        rc = proc.poll()
        now = time.time()

        if now - last_beat >= float(heartbeat_interval_seconds):
            last_beat = now
            try:
                heartbeat_callback({"running_seconds": now - started})
            except Exception:
                pass

        if rc is not None:
            break

        time.sleep(1.0)

    t_out.join(timeout=1.0)
    t_err.join(timeout=1.0)

    if rc != 0:
        stdout_txt = "".join(list(stdout_tail))[-4000:]
        stderr_txt = "".join(list(stderr_tail))[-4000:]
        logger.error(
            "exec.failed",
            returncode=rc,
            stdout=stdout_txt,
            stderr=stderr_txt,
        )
        raise subprocess.CalledProcessError(rc, list(args), output=stdout_txt, stderr=stderr_txt)
