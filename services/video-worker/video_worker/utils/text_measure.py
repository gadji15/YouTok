from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import ImageFont

_ASS_TAG_RE = re.compile(r"\{[^}]*\}")
_RTL_RE = re.compile(r"[\u0590-\u08FF]")


def strip_ass_tags(text: str) -> str:
    return _ASS_TAG_RE.sub("", text)


def contains_rtl(text: str) -> bool:
    return _RTL_RE.search(text) is not None


def prepare_text_for_ass(text: str, *, rtl: bool) -> str:
    if not rtl:
        return text

    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def _font_assets_dir() -> Path:
    # video_worker/utils -> video_worker
    return Path(__file__).resolve().parents[1] / "assets" / "fonts"


def _first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists() and p.is_file():
            return p
    return None


@lru_cache(maxsize=1)
def resolve_font_path(*, prefer_arabic: bool = False) -> Path | None:
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
        text = prepare_text_for_ass(text, rtl=True)

    font = _load_font(str(font_path) if font_path is not None else None, int(font_size))

    if hasattr(font, "getlength"):
        return int(round(float(font.getlength(text))))

    bbox = font.getbbox(text)
    return int(round(float(bbox[2] - bbox[0])))
