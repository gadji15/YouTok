from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_ASS_TAG_RE = re.compile(r"\{[^}]*\}")


def strip_ass_tags(text: str) -> str:
    # Remove ASS override blocks like {\pos(...)} or {\k20}.
    return _ASS_TAG_RE.sub("", text)


@lru_cache(maxsize=1)
def resolve_font_path() -> Path | None:
    """Best-effort resolution of a TrueType font file.

    We prefer Noto Sans (installed in the video-worker Docker image), and fall back
    to DejaVu Sans.
    """

    candidates = [
        # Debian paths (fonts-noto-core)
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        # DejaVu fallback (fonts-dejavu-core)
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]

    for p in candidates:
        if p.exists() and p.is_file():
            return p

    roots = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
    ]

    want = {"notosans-regular.ttf", "dejavusans.ttf"}

    for root in roots:
        if not root.exists():
            continue
        try:
            for p in root.rglob("*.ttf"):
                if p.name.lower() in want:
                    return p
        except Exception:
            continue

    return None


@lru_cache(maxsize=128)
def _load_font(font_path: str | None, font_size: int):
    from PIL import ImageFont

    if font_path:
        return ImageFont.truetype(font_path, int(font_size))
    return ImageFont.load_default()


def measure_text_width_px(*, text: str, font_path: Path | None, font_size: int) -> int:
    """Measure rendered text width in pixels using Pillow."""

    text = strip_ass_tags(text)
    if text == "":
        return 0

    font = _load_font(str(font_path) if font_path is not None else None, int(font_size))

    if hasattr(font, "getlength"):
        return int(round(float(font.getlength(text))))

    bbox = font.getbbox(text)
    return int(round(float(bbox[2] - bbox[0])))
