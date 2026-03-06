from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont


_RTL_RE = re.compile(r"[\u0590-\u08FF]")
_ASS_TAG_RE = re.compile(r"\{[^}]*\}")


def contains_rtl(text: str) -> bool:
    return _RTL_RE.search(text) is not None


def strip_ass_tags(text: str) -> str:
    # Remove ASS override blocks like {\pos(...)} or {\k20}.
    return _ASS_TAG_RE.sub("", text)


def _shape_rtl(text: str) -> str:
    from arabic_reshaper import reshape
    from bidi.algorithm import get_display

    reshaped = reshape(text)
    return get_display(reshaped)


def prepare_text_for_ass(text: str, *, rtl: bool) -> str:
    if not rtl:
        return text
    return _shape_rtl(text)


def _font_assets_dir() -> Path:
    # video_worker/utils -> video_worker
    return Path(__file__).resolve().parents[1] / "assets" / "fonts"


def _first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists() and p.is_file():
            return p
    return None


@lru_cache(maxsize=1)
def resolve_font_path(prefer_arabic: bool = False) -> Path | None:
    """Resolve a TrueType font file.

    Priority:
    1) Option A: fonts committed under video_worker/assets/fonts/
    2) System fonts inside the Docker image

    When prefer_arabic=True, we try Arabic-capable Noto fonts first.
    """

    assets = _font_assets_dir()

    if prefer_arabic:
        names = [
            "NotoNaskhArabic-Regular.ttf",
            "NotoSansArabic-Regular.ttf",
            "NotoSans-Regular.ttf",
            "DejaVuSans.ttf",
        ]
    else:
        names = [
            "NotoSans-Regular.ttf",
            "DejaVuSans.ttf",
        ]

    cand = _first_existing([assets / n for n in names])
    if cand is not None:
        return cand

    system_dirs = [
        Path("/usr/share/fonts/truetype/noto"),
        Path("/usr/share/fonts/opentype/noto"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
    ]

    for d in system_dirs:
        if not d.exists() or not d.is_dir():
            continue
        cand = _first_existing([d / n for n in names])
        if cand is not None:
            return cand

    # Last resort: slow search.
    want = {n.lower() for n in names}
    for root in [Path("/usr/share/fonts"), Path("/usr/local/share/fonts")]:
        if not root.exists():
            continue
        try:
            for p in root.rglob("*.ttf"):
                if p.name.lower() in want:
                    return p
        except Exception:
            continue

    return None


@lru_cache(maxsize=256)
def _load_font(font_path: str | None, font_size: int):
    if font_path:
        return ImageFont.truetype(font_path, int(font_size))
    return ImageFont.load_default()


def measure_text_width_px(*, text: str, font_path: Path | None, font_size: int, rtl: bool = False) -> int:
    """Measure rendered text width in pixels using Pillow."""

    text = strip_ass_tags(text)
    if text == "":
        return 0

    if rtl:
        text = _shape_rtl(text)

    font = _load_font(str(font_path) if font_path is not None else None, int(font_size))

    if hasattr(font, "getlength"):
        return int(round(float(font.getlength(text))))

    bbox = font.getbbox(text)
    return int(round(float(bbox[2] - bbox[0])))
