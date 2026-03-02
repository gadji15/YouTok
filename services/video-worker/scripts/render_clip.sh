#!/usr/bin/env sh
set -eu

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <clip.mp4> <subtitles.ass> <out.mp4> [crf]" >&2
  exit 2
fi

IN="$1"
ASS="$2"
OUT="$3"
CRF="${4:-18}"

# Typical TikTok-friendly encode with libass burn.
ffmpeg -y -hide_banner -loglevel error \
  -i "$IN" \
  -vf "ass=${ASS},format=yuv420p" \
  -c:v libx264 -preset slow -crf "$CRF" \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  "$OUT"
