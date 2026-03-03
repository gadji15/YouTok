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


def make_ass_header(play_res_x: int = 1080, play_res_y: int = 1920, margin_l: int = 120, margin_r: int = 120) -> str:
    header = [
        "[Script Info]",
        f"Title: generated",
        f"PlayResX: {play_res_x}",
        f"PlayResY: {play_res_y}",
        "ScriptType: v4.00+",
        "Collisions: Normal",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Arial,42,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,2,2,{margin_l},{margin_r},10,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    return "\n".join(header) + "\n"


def group_words_to_lines(words: List[Dict], max_chars: int = 40) -> List[Tuple[str, float, float]]:
    """Group words into lines/events. Returns list of (text, start, end).

    Simple greedy segmenter: add words until combined length > max_chars then flush.
    """
    lines: List[Tuple[str, float, float]] = []
    cur_words: List[str] = []
    cur_start = None
    cur_end = None
    for w in words:
        token = w.get("word", "").strip()
        if token == "":
            continue
        if cur_start is None:
            cur_start = w["start_seconds"] if isinstance(w, dict) else w[2]
        cur_end = w.get("end_seconds", cur_start)
        if cur_words and (len(" ".join(cur_words + [token])) > max_chars):
            lines.append((" ".join(cur_words), cur_start, cur_end))
            cur_words = [token]
            cur_start = w.get("start_seconds", cur_start)
        else:
            cur_words.append(token)
    if cur_words:
        lines.append((" ".join(cur_words), cur_start or 0.0, cur_end or cur_start or 0.0))
    return lines


def compute_position_default(play_res_x: int, play_res_y: int, margin_v: int = 60) -> Tuple[int, int]:
    # bottom-center default position
    x = play_res_x // 2
    y = play_res_y - margin_v
    return x, y


def try_repo_placement(video_path: Path, start: float, end: float) -> int:
    """Attempt to call into the repo's subtitle_placement module to compute a Y position.

    If the module is not importable, return None (caller will use default).
    """
    try:
        # add repo root to path (two levels up from this file)
        repo_root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(repo_root))
        from services.video_worker.video_worker.pipeline.subtitle_placement import choose_subtitle_placement

        # choose_subtitle_placement expects frame times and video path in repo; we call with simple args
        candidate = choose_subtitle_placement(str(video_path), float(start), float(end))
        # If it returns a dict with 'y' or tuple, adapt
        if isinstance(candidate, dict) and "y" in candidate:
            return int(candidate["y"])
        if isinstance(candidate, tuple) and len(candidate) >= 2:
            return int(candidate[1])
    except Exception as e:
        logger.debug("repo placement not available: %s", e)
    return None


def write_ass(out: Path, lines: List[Tuple[str, float, float]], video: Path, play_res_x: int, play_res_y: int):
    out.parent.mkdir(parents=True, exist_ok=True)
    hdr = make_ass_header(play_res_x=play_res_x, play_res_y=play_res_y)
    with out.open("w", encoding="utf-8") as fh:
        fh.write(hdr)

        for text, start, end in lines:
            # determine y position using repo placement if possible
            y = try_repo_placement(video, start, end)
            if y is None:
                x, y = compute_position_default(play_res_x, play_res_y)
            # ASS time format requires H:MM:SS.cc (centiseconds)
            start_ts = seconds_to_ass_time(start)
            end_ts = seconds_to_ass_time(end)
            # escape commas
            safe_text = text.replace("\n", " ").replace(",", "\,")
            # Use \\pos to place precisely
            ev = f"Dialogue: 0,{start_ts},{end_ts},Default,,0000,0000,0000,,{{\\pos({x},{y})}}{safe_text}\n"
            fh.write(ev)
    logger.info("wrote ASS %s with %d events", out, len(lines))


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate ASS from word-level JSON")
    p.add_argument("--words", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--play-res-x", type=int, default=1080)
    p.add_argument("--play-res-y", type=int, default=1920)
    p.add_argument("--max-chars", type=int, default=40)
    args = p.parse_args(argv)

    words = read_words(args.words)
    if not words:
        logger.error("no words in %s", args.words); return 2

    lines = group_words_to_lines(words, max_chars=args.max_chars)
    write_ass(args.out, lines, args.video, args.play_res_x, args.play_res_y)


if __name__ == "__main__":
    main()
