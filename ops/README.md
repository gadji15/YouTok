# Ops / industrialisation

## Démarrer le stack (sans Caddy)

Exemple (équivalent à ce que vous faites déjà) :

```bash
docker compose --env-file .env -f docker-compose.prod.yml up -d --build db redis backend queue web video-worker-api video-worker-worker
```

Si vous avez besoin d'exposer l'app sans domaine, `docker-compose.prod.yml` mappe maintenant `web` sur `3000:3000`.

## systemd (exemple)

Copiez `ops/systemd/aiclip-compose.service` sur le serveur (ex: `/etc/systemd/system/aiclip-compose.service`) puis adaptez :

- `WorkingDirectory=` vers le chemin du repo
- `EnvironmentFile=` vers votre `.env`

Ensuite :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aiclip-compose
sudo systemctl status aiclip-compose
```

## Observabilité

### Video-worker Prometheus metrics

Le service `video-worker-api` expose (par défaut) :

- `GET /health`
- `GET /metrics` (Prometheus)

Variables d'env :

- `VIDEO_WORKER_METRICS_ENABLED=true|false`

Exemple de config Prometheus : `ops/prometheus/prometheus.yml`.

### Sentry (optionnel)

Variables d'env (video-worker) :

- `VIDEO_WORKER_SENTRY_DSN=...`
- `VIDEO_WORKER_SENTRY_TRACES_SAMPLE_RATE=0.0` (mettre 0.05–0.2 si vous voulez du tracing)

## pm2 (optionnel, hors Docker)

Pour lancer `services/tiktok-bot` en process manager sur un serveur (sans container) :

```bash
cd services/tiktok-bot
npm install --omit=dev
pm2 start ecosystem.config.cjs
pm2 save
```

## Scripts

- `ops/scripts/prod-up.sh`
- `ops/scripts/prod-down.sh`
