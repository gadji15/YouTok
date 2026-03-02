# AI Clip SaaS

Plateforme SaaS (V1: usage interne / admin unique) qui transforme une vidéo YouTube en clips verticaux (TikTok/Reels/Shorts) avec transcription, sous-titres stylisés, scoring “viral” heuristique et export.

## Stack

- **Backend**: Laravel (scaffoldé automatiquement via `backend-bootstrap/`), Blade UI + auth (Breeze)
- **DB**: MySQL (via Docker)
- **Queue**: Laravel database queue
- **Video worker (optionnel)**: Python (FastAPI + RQ), yt-dlp, ffmpeg, Whisper
- **TikTok bot (optionnel / Phase 3)**: Node.js + Playwright (squelette)

## Démarrage (local)

Prérequis: Docker + Docker Compose.

```bash
cp .env.example .env
make up
```

Ouvrir: http://localhost:8080

## Déploiement (prod, Docker + Caddy)

Prérequis: un DNS qui pointe `${DOMAIN}` vers la machine.

```bash
cp .env.example .env
# puis éditez .env (DOMAIN, ACME_EMAIL, APP_URL, secrets, mots de passe DB)

docker compose -f docker-compose.prod.yml up -d --build
```

Identifiants par défaut (voir `.env`):
- email: `admin@example.com`
- password: `password`

### Activer le video-worker

```bash
make up-video-worker
```

Puis mettez dans `.env`:

```env
VIDEO_WORKER_BASE_URL=http://video-worker-api:8000
```

## Flux (V1)

1. Admin se connecte, crée un projet avec une URL YouTube.
2. Laravel crée le projet (status `queued`) et **enqueue** `SubmitVideoWorkerJob`.
3. Le job appelle l’API du video-worker (`POST /jobs`) avec `callback_url` + `callback_secret`.
4. Le worker exécute le pipeline puis appelle `POST /api/worker/callback` et upsert les clips.

## Sécurité (V1)

- UI: routes protégées par auth + email admin (`ADMIN_EMAILS`).
- API interne: `POST /api/projects` protégé par `X-Internal-Secret`.
- Callback worker: `POST /api/worker/callback` protégé par `X-Callback-Secret`.

## Commandes utiles

```bash
make logs
make queue-logs
make backend-shell
```
