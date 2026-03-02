from __future__ import annotations

import subprocess

import httpx


def format_exception_short(exc: Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        tail = stderr[-800:] if stderr else (stdout[-800:] if stdout else "")
        details = f"returncode={exc.returncode}"
        if tail:
            return f"CalledProcessError({details}): {tail}"
        return f"CalledProcessError({details})"

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = (exc.response.text or "").strip()
        tail = body[:300]
        if tail:
            return f"HTTPStatusError(status_code={status}): {tail}"
        return f"HTTPStatusError(status_code={status})"

    msg = str(exc).strip()
    if msg:
        return f"{type(exc).__name__}: {msg}"
    return type(exc).__name__
