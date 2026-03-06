# Text-aware dynamic crop (Option A MVP)

This repo includes a best-effort **OCR-guided dynamic vertical crop** used to keep on-screen captions/subtitles inside frame while reframing 16:9 → 9:16.

## Enable (video-worker pipeline)

Set:

- `VIDEO_WORKER_TEXT_AWARE_CROP_ENABLED=true`

Optional tuning:

- `VIDEO_WORKER_TEXT_AWARE_CROP_SAMPLE_FPS` (default: `5.0`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_PADDING_RATIO` (default: `0.18`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_OCR_LANG` (default: `eng+fra+ara`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_OCR_CONF_THRESHOLD` (default: `60.0`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_MIN_ZOOM` / `VIDEO_WORKER_TEXT_AWARE_CROP_MAX_ZOOM` (defaults: `1.0` / `1.9`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_READING_HOLD_SEC` (default: `0.8`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_DEBUG_FRAMES` (default: `false`)

Artifacts per clip:

- `<output_dir>/<clip_id>/text_aware_crop/reframed.mp4`
- `<output_dir>/<clip_id>/text_aware_crop/crop_keyframes.json`
- `<output_dir>/<clip_id>/text_aware_crop/metrics.json`

## CLI

```bash
python -m video_worker.tools.text_aware_crop \
  --input input.mp4 \
  --output out.mp4 \
  --config video_worker/tools/text_aware_crop_config.example.yaml
```

## Dependencies

- `ffmpeg`
- `tesseract-ocr` + language packs
- Python: `pytesseract` (and `opencv-python` / `mediapipe` already used elsewhere)
