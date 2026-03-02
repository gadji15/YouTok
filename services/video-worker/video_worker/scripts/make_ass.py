from __future__ import annotations

import argparse
from pathlib import Path

from video_worker.pipeline.subtitles import write_word_level_ass_for_clip
from video_worker.pipeline.word_alignment import load_words_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate .ass subtitles from words.json")
    parser.add_argument("words_json", type=Path, help="Path to words.json")
    parser.add_argument("--output", type=Path, default=Path("subtitles.ass"))

    parser.add_argument("--clip-start", type=float, default=0.0)
    parser.add_argument("--clip-end", type=float, default=999999.0)

    parser.add_argument("--template", type=str, default="modern_karaoke")

    parser.add_argument("--play-res-x", type=int, default=1080)
    parser.add_argument("--play-res-y", type=int, default=1920)

    parser.add_argument(
        "--position",
        choices=["bottom", "top"],
        default="bottom",
        help="Fixed placement. (The video-worker pipeline uses auto placement.)",
    )

    args = parser.parse_args()

    words = load_words_json(args.words_json)

    if args.position == "top":
        placement = (8, args.play_res_x // 2, int(max(args.play_res_y * 0.08, 120)))
    else:
        placement = (
            2,
            args.play_res_x // 2,
            args.play_res_y - int(max(args.play_res_y * 0.08, 120)),
        )

    write_word_level_ass_for_clip(
        clip_start_seconds=float(args.clip_start),
        clip_end_seconds=float(args.clip_end),
        words=words,
        output_path=args.output,
        placement=placement,
        play_res_x=int(args.play_res_x),
        play_res_y=int(args.play_res_y),
        template=args.template,
    )


if __name__ == "__main__":
    main()
