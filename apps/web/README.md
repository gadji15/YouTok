# YouTok Web (Next.js)

This folder contains the standalone Next.js frontend for YouTok.

## Dev

1) Start the Laravel backend (from repo root):

```bash
make up
```

2) Start Next.js (from `apps/web`):

```bash
# Required (server-only) env vars used to talk to Laravel internal API.
# Defaults match docker-compose.yml.
export LARAVEL_BASE_URL="http://127.0.0.1:8080"
export INTERNAL_API_SECRET="please-change-to-a-long-random-string"

npm install
npm run dev
```

Then open: http://localhost:3000

### Running Next.js inside Docker

If you run the Next.js server inside Docker, `127.0.0.1` will point to the container.
Use the Docker service name instead:

```bash
export LARAVEL_BASE_URL="http://backend:8000"
```

## i18n

- Supported locales: `fr`, `en`
- Locale is stored in `youtok_locale` cookie.
- URLs are currently locale-prefixed: `/<locale>/...`.

