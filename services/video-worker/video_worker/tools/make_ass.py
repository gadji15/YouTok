#!/usr/bin/env python3
"""make_ass.py

Generate an ASS subtitle file from a `words.json` produced by
`whisperx_align.py` or similar. This script supports a simple placement
strategy and can call into the repo's `subtitle_placement` module when
available to compute a safer `y` placement (avoiding faces).

Usage:
  python make_ass.py --words words.json --out out.ass --video sample.mp4

Output: ASS file written to `--out`.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# NOTE: This module is used in production (called from clip.py) and also imported
# in unit tests. Keep it dependency-free.


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("make_ass")


def read_words(path: Path) -> List[Dict]:
    j = json.loads(path.read_text(encoding="utf-8"))
    # Expect list of {word,start_seconds,end_seconds,confidence}
    return j


def seconds_to_ass_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:d}:{m:02d}:{sec:06.3f}"[:-1]  # ASS wants H:MM:SS.cs (centiseconds) - trim micro


def make_ass_header(
    *,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    margin_l: int = 120,
    margin_r: int = 120,
    template: str = "modern_karaoke",
) -> str:
    template = (template or "modern_karaoke").lower().strip()

    # Match the in-repo ASS templates more closely.
    # - Larger font for 1080x1920
    # - Stronger outline for readability
    if template in {"cinematic", "cinematic_karaoke"}:
        style = f"Style: Default,Noto Sans,66,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,1,0,0,0,100,100,0,0,1,7,1,2,{margin_l},{margin_r},170,1"
    else:
        style = f"Style: Default,Noto Sans,62,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,0,2,{margin_l},{margin_r},160,1"

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


def join_tokens(tokens: List[str]) -> str:
    out: List[str] = []
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


def group_words_to_lines(words: List[Dict], max_chars: int = 40) -> List[Tuple[str, float, float]]:
    """Group words into lines/events. Returns list of (text, start, end).

    Simple greedy segmenter: add words until combined length > max_chars then flush.

    Important: end time must be the end of the *last word actually included* in the line.
    Otherwise consecutive events overlap.
    """

    lines: List[Tuple[str, float, float]] = []
    cur_words: List[str] = []
    cur_start: float | None = None
    cur_end: float | None = None

    for w in words:
        token = w.get("word", "").strip()
        if token == "":
            continue

        w_start = float(w.get("start_seconds", 0.0))
        w_end = float(w.get("end_seconds", w_start))

        if cur_start is None:
            cur_start = w_start

        # Check if this token would overflow the current line.
        if cur_words:
            candidate = join_tokens(cur_words + [token])
            if len(candidate) > max_chars:
                # Flush without consuming current token.
                lines.append((join_tokens(cur_words), float(cur_start), float(cur_end or cur_start)))
                cur_words = []
                cur_start = w_start
                cur_end = None

        cur_words.append(token)
        cur_end = w_end

    if cur_words:
        lines.append((join_tokens(cur_words), float(cur_start or 0.0), float(cur_end or cur_start or 0.0)))

    return lines


def compute_position_default(
    *,
    play_res_x: int,
    play_res_y: int,
    ui_safe_ymin: float = 0.78,
) -> Tuple[int, int]:
    # bottom-center, but above the UI safe zone.
    x = play_res_x // 2
    safe_y = int(play_res_y * ui_safe_ymin)
    y = max(0, safe_y - int(max(play_res_y * 0.06, 110)))
    return x, y


def write_ass(
    *,
    out: Path,
    lines: List[Tuple[str, float, float]],
    play_res_x: int,
    play_res_y: int,
    x: int | None,
    y: int | None,
    an: int,
    template: str,
    ui_safe_ymin: float,
):
    out.parent.mkdir(parents=True, exist_ok=True)
    hdr = make_ass_header(
        play_res_x=play_res_x,
        play_res_y=play_res_y,
        template=template,
    )

    if x is None or y is None:
        x, y = compute_position_default(play_res_x=play_res_x, play_res_y=play_res_y, ui_safe_ymin=ui_safe_ymin)

    with out.open("w", encoding="utf-8") as fh:
        fh.write(hdr)

        for text, start, end in lines:
            start_ts = seconds_to_ass_time(float(start))
            end_ts = seconds_to_ass_time(float(end))

            # escape commas
            safe_text = text.replace("\n", " ").replace(",", "\\,")

            # Use \an + \pos to place precisely.
            # Add a small blur to improve readability.
            ev = (
                f"Dialogue: 0,{start_ts},{end_ts},Default,,0000,0000,0000,,"
                f"{{\\an{int(an)}\\pos({int(x)},{int(y)})\\blur2}}{safe_text}\n"
            )
            fh.write(ev)

    logger.info("wrote ASS %s with %d events", out, len(lines))


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate ASS from word-level JSON")
    p.add_argument("--words", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--video", required=False, type=Path)  # kept for backward compatibility
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

    lines = group_words_to_lines(words, max_chars=int(args.max_chars))

    write_ass(
        out=args.out,
        lines=lines,
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
    main()
