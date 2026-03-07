# tiktok-bot

Node service for publishing generated clips to TikTok.

This is still **Phase 3 WIP** (TikTok automation requires iterative hardening), but it includes:
- background job queueing + status tracking
- retry/backoff wiring
- failure artifacts (screenshots / JSON / HTML) written to disk

## API

Public:
- `GET /health` → `{ "status": "ok" }`

Internal (requires header `X-Internal-Secret: <PUBLISH_INTERNAL_SECRET|INTERNAL_API_SECRET>`):
- `POST /publish`
  - Body: `{ clip_path, caption, account_id, privacy?, allow_comments?, allow_duet?, allow_stitch? }`
  - `clip_path` must point to a file **inside** `PUBLISH_CLIP_ROOT` (default `/shared`).
  - Returns: `202 Accepted` with `{ job_id, mode, queue_driver }`

- `GET /jobs/:id`
  - Returns job status (`queued|active|completed|failed|...`)

- `GET /accounts`
  - Returns `{ accounts: ["acct_1", ...] }` based on cookie files.

- `GET /accounts/:id/storage-state`
  - Returns the saved Playwright `storageState` JSON.

- `PUT /accounts/:id/storage-state`
  - Body: Playwright `storageState` JSON.

## Environment variables

- `PUBLISH_INTERNAL_SECRET` (optional) / `INTERNAL_API_SECRET` (recommended)
  - Header shared with the backend (`X-Internal-Secret`).
  - In docker-compose, we reuse `INTERNAL_API_SECRET`.

- `PUBLISH_CLIP_ROOT` (default: `/shared`)
  - `clip_path` must be inside this root (path traversal protection).

- `PUBLISH_MODE` = `stub` | `playwright` | `tiktok_api` (default: `stub`)
- `PUBLISH_REDIS_URL` (optional)
  - If set, uses **BullMQ + Redis** for job queueing.
  - If unset, falls back to an in-memory queue (useful for tests).
- `PUBLISH_ATTEMPTS` (default: `3`)
- `PUBLISH_BACKOFF_SECONDS` (default: `30`)
- `PUBLISH_CONCURRENCY` (default: `1`)
- `PUBLISH_ARTIFACT_DIR` (default: `/app/storage/artifacts` in Docker; otherwise `./storage/artifacts`)

## Storage

- Cookies: `./storage/cookies/<account_id>.json`
- Job artifacts: `./storage/artifacts/<job_id>/...`

Security note: treat the storage directory as sensitive.

## Playwright notes

`PUBLISH_MODE=playwright` performs a best-effort upload flow:
- opens `tiktok.com/upload`
- selects the clip file
- fills caption
- attempts to set Privacy=Public and enable comments/duet/stitch
- clicks Post

Because TikTok UI/anti-bot measures can change, this may occasionally fail (captcha, logged-out, UI changes).
When it fails, the job artifacts directory contains screenshots + HTML for debugging.

Session management:
- The bot relies on a saved Playwright `storageState` per account:
  - `./storage/cookies/<account_id>.json`
- Helper script (run locally, opens a browser window):
  - `npm run login -- <account_id>`
- You can also manage it via API:
  - `PUT /accounts/:id/storage-state`
  - `GET /accounts/:id/storage-state`
