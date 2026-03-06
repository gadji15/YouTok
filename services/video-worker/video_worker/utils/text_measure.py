from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import ImageFont


_RTL_RE = re.compile(r"[\u0590-\u08FF]")
_ASS_TAG_RE = re.compile(r"\{[^}]*\}")


def contains_rtl(text: str) -> bool:
    return _RTL_RE.search(text) is not None


def strip_ass_tags(text: str) -> str:
    return _ASS_TAG_RE.sub("", text)


def prepare_text_for_measure(text: str, *, rtl: bool) -> str:
    if not rtl:
        return text

    # Apply Arabic shaping + bidi reordering for correct visual width measurement.
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def prepare_text_for_ass(text: str, *, rtl: bool) -> str:
    # We do the same transformation for ASS output to avoid broken shaping in renderers.
    return prepare_text_for_measure(text, rtl=rtl)


def _font_assets_dir() -> Path:
    # video_worker/utils -> video_worker
    return Path(__file__).resolve().parents[1] / "assets" / "fonts"


def _existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists() and p.is_file():
            return p
    return None


def resolve_font_path(*, prefer_arabic: bool) -> Path | None:
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

    # Option A (preferred): font files committed alongside the worker.
    cand = _existing([assets / n for n in names])
    if cand is not None:
        return cand

    # Fallback: system fonts (Docker image installs fonts-noto-core + fonts-dejavu-core).
    system_dirs = [
        Path("/usr/share/fonts/truetype/noto"),
        Path("/usr/share/fonts/opentype/noto"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts"),
    ]

    for d in system_dirs:
        if not d.exists() or not d.is_dir():
            continue
        cand = _existing([d / n for n in names])
        if cand is not None:
            return cand

    return None


@lru_cache(maxsize=256)
def _get_font(*, font_path: str | None, font_size: int):
    if font_path:
        return ImageFont.truetype(font_path, int(font_size))
    return ImageFont.load_default()


def measure_text_width_px(*, text: str, font_path: Path | None, font_size: int, rtl: bool) -> int:
    text = strip_ass_tags(text)
    text = prepare_text_for_measure(text, rtl=rtl)

    font = _get_font(font_path=str(font_path) if font_path is not None else None, font_size=int(font_size))

    if hasattr(font, "getlength"):
        w = float(font.getlength(text))
    else:
        bbox = font.getbbox(text)
        w = float(bbox[2] - bbox[0])

    return int(round(w))
