# video-worker

Python service that accepts YouTube video processing jobs, runs a clip-generation pipeline, and posts results back to a Laravel callback.

## Components

- FastAPI API server (`video_worker.api:app`)
  - `POST /jobs` enqueue a job into Redis via RQ
  - `GET /health` basic liveness + Redis ping
  - `GET /metrics` Prometheus metrics (when `VIDEO_WORKER_METRICS_ENABLED=true`)
- RQ worker process (`python -m video_worker.worker`)
  - executes the pipeline steps and posts results to the provided callback URL

## Environment variables

See `video_worker/config.py` for the full list.

Common:

- `VIDEO_WORKER_REDIS_URL` (required) e.g. `redis://redis:6379/0`
- `VIDEO_WORKER_QUEUE_NAME` (default: `video-worker`)
- `VIDEO_WORKER_STORAGE_PATH` (default: `/shared/storage`)
- `VIDEO_WORKER_WHISPER_MODEL` (default: `base`)
- `VIDEO_WORKER_WHISPER_DEVICE` (default: `auto`; one of `auto`, `cpu`, `cuda`, `mps`)
- `VIDEO_WORKER_WHISPER_TEMPERATURE` (default: `0.0`)
- `VIDEO_WORKER_WHISPER_BEAM_SIZE` (default: `1`)
- `VIDEO_WORKER_WHISPER_BEST_OF` (default: `1`)
- `VIDEO_WORKER_CLIP_MIN_SECONDS` (default: `60`)
- `VIDEO_WORKER_CLIP_MAX_SECONDS` (default: `180`)
- `VIDEO_WORKER_SUBTITLES_ENABLED` (default: `true`)
- `VIDEO_WORKER_SUBTITLE_TEMPLATE` (default: `modern_karaoke`; one of `default`, `modern`, `karaoke`, `modern_karaoke`, `cinematic`, `cinematic_karaoke`, `storytelling`, `podcast`, `motivation`)
- `VIDEO_WORKER_SUBTITLE_MAX_WORDS_PER_LINE` (default: `6`)
- `VIDEO_WORKER_SUBTITLE_MAX_CHARS_PER_LINE` (default: `36`)
- `VIDEO_WORKER_SUBTITLE_CLIP_REALIGN_ENABLED` (default: `false`; enables slow per-clip word re-alignment for tighter timings)
- `VIDEO_WORKER_TITLE_PROVIDER` (default: `heuristic`; one of `heuristic`, `openai`)
- `VIDEO_WORKER_OPENAI_API_KEY` (default: empty; required when `TITLE_PROVIDER=openai`)
- `VIDEO_WORKER_OPENAI_MODEL` (default: `gpt-4.1-mini`)
- `VIDEO_WORKER_OPENAI_BASE_URL` (default: `https://api.openai.com/v1`)
- `VIDEO_WORKER_TARGET_FPS` (default: `30`)

Text-aware dynamic crop (Option A MVP; requires tesseract + OCR deps):

- `VIDEO_WORKER_TEXT_AWARE_CROP_ENABLED` (default: `false`; only affects `output_aspect=vertical`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_SAMPLE_FPS` (default: `5.0`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_PADDING_RATIO` (default: `0.18`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_OCR_LANG` (default: `eng+fra+ara`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_OCR_CONF_THRESHOLD` (default: `60.0`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_MIN_ZOOM` (default: `1.0`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_MAX_ZOOM` (default: `1.9`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_READING_HOLD_SEC` (default: `0.8`)
- `VIDEO_WORKER_TEXT_AWARE_CROP_DEBUG_FRAMES` (default: `false`)

- `VIDEO_WORKER_ENABLE_LOUDNORM` (default: `false`)
- `VIDEO_WORKER_LOG_LEVEL` (default: `INFO`)
- `VIDEO_WORKER_METRICS_ENABLED` (default: `true`)
- `VIDEO_WORKER_SENTRY_DSN` (default: empty)
- `VIDEO_WORKER_SENTRY_TRACES_SAMPLE_RATE` (default: `0.0`)
- `VIDEO_WORKER_CALLBACK_MAX_RETRIES` (default: `3`)
- `VIDEO_WORKER_CALLBACK_RETRY_BACKOFF_SECONDS` (default: `0.5`)
- `VIDEO_WORKER_DOWNLOAD_MAX_RETRIES` (default: `2`)
- `VIDEO_WORKER_DOWNLOAD_RETRY_BACKOFF_SECONDS` (default: `1.0`)

API hardening (optional):
- `VIDEO_WORKER_API_KEY` (default: empty). If set, `POST /jobs` requires `Authorization: Bearer <key>`.
- `VIDEO_WORKER_CALLBACK_HOST_ALLOWLIST` (default: empty). If set, rejects jobs where `callback_url.host` is not in the comma-separated allowlist.

Artifact storage (S3 / R2 / MinIO):

If `VIDEO_WORKER_S3_BUCKET` is set, the worker uploads completed artifacts to object storage and returns public URLs in the callback payload.

- `VIDEO_WORKER_S3_BUCKET` (required to enable)
- `VIDEO_WORKER_S3_PREFIX` (default: `hikma`)
- `VIDEO_WORKER_S3_REGION` (optional)
- `VIDEO_WORKER_S3_ENDPOINT_URL` (optional; for MinIO/R2)
- `VIDEO_WORKER_S3_ACCESS_KEY_ID` / `VIDEO_WORKER_S3_SECRET_ACCESS_KEY`
- `VIDEO_WORKER_S3_PUBLIC_BASE_URL` (optional; if set, URLs are `<base>/<key>`)
- `VIDEO_WORKER_S3_CLEANUP_LOCAL` (default: `false`)

## Run locally

On Debian/Ubuntu with Python 3.12+, you may see `error: externally-managed-environment` (PEP 668) if you try to `pip install` system-wide. Use a virtualenv.

```bash
python3 -m venv .venv
. .venv/bin/activate

# Light install (enough for unit tests + API scaffolding)
pip install -r requirements.txt -r requirements-dev.txt

# Full pipeline (includes Whisper + WhisperX alignment; heavy)
# pip install -r requirements-ml.txt

# API
export VIDEO_WORKER_REDIS_URL=redis://localhost:6379/0
uvicorn video_worker.api:app --host 0.0.0.0 --port 8000

# Worker (separate terminal)
export VIDEO_WORKER_REDIS_URL=redis://localhost:6379/0
python -m video_worker.worker
```

### Run tests

```bash
. .venv/bin/activate
python -m pytest -q
```

### Subtitle/UI tuning

The worker uses a simple "bottom UI zone" model to avoid subtitles overlapping TikTok UI.

- `VIDEO_WORKER_UI_SAFE_YMIN` (default: `0.78`): relative Y (0..1) where the bottom UI zone starts.
  - `0.78` means the bottom ~22% is considered UI.

Quality gate (optional):

- `VIDEO_WORKER_QUALITY_GATE_ENABLED` (default: `false`)
- `VIDEO_WORKER_QUALITY_GATE_FACE_OVERLAP_P95_THRESHOLD` (default: `0.05`)
- `VIDEO_WORKER_QUALITY_GATE_MAX_ATTEMPTS` (default: `2`)

When enabled, each clip can be rendered multiple times with alternative subtitle placements until
`face_overlap_ratio_p95 <= threshold` (measured on the final rendered video).

If you don't have `venv` support installed, on Debian/Ubuntu you typically need:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv
```

## Job callback payload

The worker POSTs JSON to `callback_url` with header:

- `X-Callback-Secret: <callback_secret>`

`status` is one of:

- `queued` (API accepted job and enqueued it)
- `processing` (worker started)
- `completed` (pipeline finished; `artifacts` populated)
- `failed` (pipeline failed; `error` set; `artifacts` may be partially populated)

Payload shape:

```json
{
  "job_id": "...",
  "project_id": "...",
  "status": "completed",
  "artifacts": {
    "source_video_path": "...",
    "audio_path": "...",
    "transcript_json_path": "...",
    "subtitles_srt_path": "...",
    "clips_json_path": "...",
    "words_json_path": "...",
    "segments_json_path": "...",
    "source_metadata_json_path": "...",
    "source_thumbnail_path": "...",
    "clips": [
      {
        "clip_id": "clip_001",
        "start_seconds": 12.3,
        "end_seconds": 42.9,
        "score": 0.82,
        "reason": "question_hook,pattern_interrupt",
        "video_path": "...",
        "subtitles_ass_path": "...",
        "subtitles_srt_path": "...",
        "title": "..."
      }
    ]
  },
  "error": null
}
```

Additional artifacts written to disk (and included in the callback payload when available):

- `projects/<project_id>/artifacts/words.json`: word-level timestamps `{word,start,end,confidence}` (WhisperX when available, otherwise heuristic fallback).
- `projects/<project_id>/artifacts/segments.json`: selected segments with `{segment_id,start_time,end_time,viral_score,text,word_timestamps}`.
- `projects/<project_id>/artifacts/source_metadata.json`: best-effort yt-dlp metadata (or ffprobe metadata for local file mode).
- `projects/<project_id>/artifacts/thumbnail.jpg`: best-effort thumbnail (YouTube mode).

## Integration test plan (curl)

This repo does not include the Laravel app, but the worker expects a Laravel callback endpoint. A reference implementation is documented in `docs/laravel-callback.md`.

1) Start Redis (example):

```bash
docker run --rm -p 6379:6379 redis:7
```

2) Start the API + worker (see “Run locally” above).

3) Sanity check API:

```bash
curl -sS http://localhost:8000/health
```

4) Manually validate your Laravel callback secret handling (replace URL/secret):

```bash
# should be 401/403
curl -i -X POST http://localhost:8080/api/worker/callback \
  -H 'Content-Type: application/json' \
  -d '{"job_id":"job_1","project_id":"proj_1","status":"completed"}'

# should be 200
curl -i -X POST http://localhost:8080/api/worker/callback \
  -H 'Content-Type: application/json' \
  -H 'X-Callback-Secret: supersecret' \
  -d '{"job_id":"job_1","project_id":"proj_1","status":"failed","error":"boom"}'
```

5) Create a job (replace URL/secret/project_id/youtube_url):

```bash
curl -sS -X POST http://localhost:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "proj_1",
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "callback_url": "http://localhost:8080/api/worker/callback",
    "callback_secret": "supersecret"
  }'
```

Local file mode (worker must be able to read the path inside its container):

```bash
curl -sS -X POST http://localhost:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "proj_1",
    "local_video_path": "/shared/uploads/source.mp4",
    "callback_url": "http://localhost:8080/api/worker/callback",
    "callback_secret": "supersecret"
  }'
```
