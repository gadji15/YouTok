#!/usr/bin/env bash
# Simple helper to burn an ASS into a video and encode a MP4 output.
# Usage: render_clip.sh input.mp4 subs.ass out.mp4

set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 input.mp4 subs.ass out.mp4 [crop_w crop_h crop_x crop_y]" >&2
  exit 2
fi

IN="$1"
ASS="$2"
OUT="$3"

# optional crop params
if [ "$#" -ge 7 ]; then
  CROP_W="$4"; CROP_H="$5"; CROP_X="$6"; CROP_Y="$7"
  CROP_FILTER="crop=${CROP_W}:${CROP_H}:${CROP_X}:${CROP_Y},"
else
  CROP_FILTER=""
fi

# Build filterchain: crop (optional) -> scale (keep original) -> ass
FILTER="${CROP_FILTER}ass='${ASS}'"

ffmpeg -y -i "$IN" -vf "$FILTER,format=yuv420p" -c:v libx264 -preset veryfast -crf 18 -c:a aac -b:a 192k "$OUT"

echo "Rendered $OUT"
