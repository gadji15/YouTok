#!/usr/bin/env python3
"""make_ass.py

Generate an ASS subtitle file from a `words.json` produced by `whisperx_align.py`.

Goals:
- No "\\," noise before punctuation.
- Keep font sizes readable across resolutions.
- Produce 1–2 line subtitles with ASS line breaks (\\N) so lines never overflow.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("make_ass")


def read_words(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [w for w in data if isinstance(w, dict)]
    return []


def seconds_to_ass_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    # ASS wants H:MM:SS.cs (centiseconds)
    return f"{h:d}:{m:02d}:{sec:06.3f}"[:-1]


def _scale_font_size(base: int, *, play_res_y: int) -> int:
    scaled = int(round(base * float(play_res_y) / 1920.0))
    return max(26, min(96, scaled))


def _style_font_size(template: str, *, play_res_y: int) -> int:
    template = (template or "modern_karaoke").lower().strip()
    if template in {"cinematic", "cinematic_karaoke"}:
        return _scale_font_size(66, play_res_y=play_res_y)
    return _scale_font_size(62, play_res_y=play_res_y)


def make_ass_header(
    *,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    margin_l: int = 120,
    margin_r: int = 120,
    template: str = "modern_karaoke",
) -> str:
    template = (template or "modern_karaoke").lower().strip()

    font_size = _style_font_size(template, play_res_y=play_res_y)

    if template in {"cinematic", "cinematic_karaoke"}:
        style = (
            f"Style: Default,Noto Sans,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,"
            f"1,0,0,0,100,100,0,0,1,7,1,2,{margin_l},{margin_r},170,1"
        )
    else:
        style = (
            f"Style: Default,Noto Sans,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,"
            f"1,0,0,0,100,100,0,0,1,6,0,2,{margin_l},{margin_r},160,1"
        )

    header = [
        "[Script Info]",
        "Title: generated",
        f"PlayResX: {play_res_x}",
        f"PlayResY: {play_res_y}",
        "ScriptType: v4.00+",
        "Collisions: Normal",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    return "\n".join(header) + "\n"


def _is_punct_token(tok: str) -> bool:
    return (
        tok in {",", ".", "!", "?", ";", ":", "…", ")", "]", "}", "»"}
        or tok.startswith("'")
        or tok.startswith("’")
    )


def _is_opening_punct(tok: str) -> bool:
    return tok in {"(", "[", "{", "«"}


def join_tokens(tokens: list[str]) -> str:
    out: list[str] = []
    for t in tokens:
        if not out:
            out.append(t)
            continue

        prev = out[-1]

        if _is_punct_token(t):
            out[-1] = prev + t
            continue

        if _is_opening_punct(prev):
            out[-1] = prev + t
            continue

        out.append(" " + t)

    return "".join(out)


def group_words_to_lines(words: list[dict[str, Any]], max_chars: int = 40) -> list[tuple[str, float, float]]:
    lines: list[tuple[str, float, float]] = []
    cur_tokens: list[str] = []
    cur_start: float | None = None
    cur_end: float | None = None

    for w in words:
        token = str(w.get("word") or "").strip()
        if token == "":
            continue

        w_start = float(w.get("start_seconds", 0.0))
        w_end = float(w.get("end_seconds", w_start))

        if cur_start is None:
            cur_start = w_start

        if cur_tokens:
            candidate = join_tokens(cur_tokens + [token])
            if len(candidate) > max_chars:
                lines.append((join_tokens(cur_tokens), float(cur_start), float(cur_end or cur_start)))
                cur_tokens = [token]
                cur_start = w_start
                cur_end = w_end
                continue

        cur_tokens.append(token)
        cur_end = w_end

    if cur_tokens:
        lines.append((join_tokens(cur_tokens), float(cur_start or 0.0), float(cur_end or cur_start or 0.0)))

    return lines


def _wrap_ass_text(text: str, *, max_chars: int) -> str:
    def _break_long_token(tok: str) -> list[str]:
        if len(tok) <= max_chars:
            return [tok]
        return [tok[i : i + max_chars] for i in range(0, len(tok), max_chars)]

    tokens = [t for t in text.split() if t]

    expanded: list[str] = []
    for t in tokens:
        expanded.extend(_break_long_token(t))

    out_lines: list[str] = []
    cur: list[str] = []
    cur_len = 0

    for tok in expanded:
        add = len(tok) + (1 if cur else 0)
        if cur and cur_len + add > max_chars:
            out_lines.append(" ".join(cur))
            cur = [tok]
            cur_len = len(tok)
        else:
            cur.append(tok)
            cur_len += add

    if cur:
        out_lines.append(" ".join(cur))

    if not out_lines:
        return ""

    if len(out_lines) > 2:
        out_lines = [out_lines[0], " ".join(out_lines[1:])]

    return "\\N".join(out_lines)


def compute_position_default(*, play_res_x: int, play_res_y: int, ui_safe_ymin: float = 0.78) -> tuple[int, int]:
    x = play_res_x // 2
    safe_y = int(play_res_y * ui_safe_ymin)
    y = max(0, safe_y - int(max(play_res_y * 0.06, 110)))
    return x, y


def write_ass(
    *,
    out: Path,
    lines: list[tuple[str, float, float]],
    play_res_x: int,
    play_res_y: int,
    x: int | None,
    y: int | None,
    an: int,
    template: str,
    ui_safe_ymin: float,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)

    margin_l = max(60, int(round(120 * float(play_res_x) / 1080.0)))
    margin_r = max(60, int(round(120 * float(play_res_x) / 1080.0)))

    hdr = make_ass_header(
        play_res_x=play_res_x,
        play_res_y=play_res_y,
        margin_l=margin_l,
        margin_r=margin_r,
        template=template,
    )

    if x is None or y is None:
        x, y = compute_position_default(play_res_x=play_res_x, play_res_y=play_res_y, ui_safe_ymin=ui_safe_ymin)

    font_size = _style_font_size(template, play_res_y=play_res_y)
    approx_char_w = max(8.0, font_size * 0.55)
    safe_width_px = max(200, int(play_res_x - margin_l - margin_r))
    max_chars = max(18, int(safe_width_px / approx_char_w))

    with out.open("w", encoding="utf-8") as fh:
        fh.write(hdr)

        for text, start, end in lines:
            start_ts = seconds_to_ass_time(float(start))
            end_ts = seconds_to_ass_time(float(end))

            safe_text = _wrap_ass_text(str(text).replace("\n", " "), max_chars=max_chars)

            fh.write(
                f"Dialogue: 0,{start_ts},{end_ts},Default,,0000,0000,0000,,"
                f"{{\\an{int(an)}\\pos({int(x)},{int(y)})\\blur2}}{safe_text}\n"
            )

    logger.info("wrote ASS %s with %d events", out, len(lines))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate ASS from word-level JSON")
    p.add_argument("--words", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--video", required=False, type=Path)
    p.add_argument("--play-res-x", type=int, default=1080)
    p.add_argument("--play-res-y", type=int, default=1920)
    p.add_argument("--max-chars", type=int, default=44)
    p.add_argument("--x", type=int, default=None)
    p.add_argument("--y", type=int, default=None)
    p.add_argument("--an", type=int, default=2)
    p.add_argument("--template", type=str, default="modern_karaoke")
    p.add_argument("--ui-safe-ymin", type=float, default=0.78)
    args = p.parse_args(argv)

    words = read_words(args.words)
    if not words:
        logger.error("no words in %s", args.words)
        return 2

    raw_lines = group_words_to_lines(words, max_chars=int(args.max_chars))

    write_ass(
        out=args.out,
        lines=raw_lines,
        play_res_x=int(args.play_res_x),
        play_res_y=int(args.play_res_y),
        x=args.x,
        y=args.y,
        an=int(args.an),
        template=str(args.template),
        ui_safe_ymin=float(args.ui_safe_ymin),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

