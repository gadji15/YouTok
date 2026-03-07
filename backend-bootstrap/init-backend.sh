#!/usr/bin/env bash
set -euo pipefail

cd /var/www/backend

is_production_env() {
  [ "${APP_ENV:-}" = "production" ]
}

if is_production_env; then
  if [ -z "${INTERNAL_API_SECRET:-}" ] || [[ "${INTERNAL_API_SECRET}" == change-me ]] || [[ "${INTERNAL_API_SECRET}" == please-change* ]]; then
    echo "[backend_init] ERROR: INTERNAL_API_SECRET must be set to a non-default value in production" >&2
    exit 1
  fi

  if [ -z "${VIDEO_WORKER_CALLBACK_SECRET:-}" ] || [[ "${VIDEO_WORKER_CALLBACK_SECRET}" == change-me-too ]] || [[ "${VIDEO_WORKER_CALLBACK_SECRET}" == please-change* ]]; then
    echo "[backend_init] ERROR: VIDEO_WORKER_CALLBACK_SECRET must be set to a non-default value in production" >&2
    exit 1
  fi

  if [ -z "${ADMIN_PASSWORD:-}" ] || [[ "${ADMIN_PASSWORD}" == password ]] || [[ "${ADMIN_PASSWORD}" == please-change* ]]; then
    echo "[backend_init] ERROR: ADMIN_PASSWORD must be changed from the default in production" >&2
    exit 1
  fi
fi

fix_env_perms() {
  if [ -f .env ]; then
    chown "${DOCKER_UID:-1000}":"${DOCKER_GID:-1000}" .env 2>/dev/null || true
    # Keep it readable in the common case where the host user ID doesn't match DOCKER_UID.
    chmod 644 .env 2>/dev/null || true
  fi
}

normalize_app_key() {
  # If APP_KEY appears multiple times, Laravel's Dotenv loader will use the first.
  # Keep exactly one (the last non-empty value).
  if [ -f .env ]; then
    local val
    val="$(grep -E '^APP_KEY=' .env | tail -n 1 | cut -d= -f2- | tr -d '[:space:]')"
    if [ -n "$val" ]; then
      sed -i '/^APP_KEY=/d' .env
      echo "APP_KEY=${val}" >> .env
    fi
    fix_env_perms
  fi
}

# If running as root (backend_init), fix ownership once then drop privileges.
if [ "$(id -u)" = "0" ]; then
  chown -R "${DOCKER_UID:-1000}":"${DOCKER_GID:-1000}" /var/www/backend || true
  chmod -R ug+rwX /var/www/backend || true

  # Ensure the shared volume is writable by the non-root runtime user (used for artifacts + uploads).
  if [ -d /shared ]; then
    chown -R "${DOCKER_UID:-1000}":"${DOCKER_GID:-1000}" /shared || true
    chmod -R ug+rwX /shared || true
  fi

  # Re-run the script as the non-root runtime user to avoid creating root-owned files
  # like backend/.env (root:root 0600).
  if [ -z "${BACKEND_INIT_DROPPED_PRIVS:-}" ] && command -v gosu >/dev/null 2>&1; then
    export BACKEND_INIT_DROPPED_PRIVS=1
    exec gosu "${DOCKER_UID:-1000}:${DOCKER_GID:-1000}" /bin/bash /bootstrap/init-backend.sh
  fi

  echo "[backend_init] WARNING: gosu not found; backend files may end up owned by root" >&2

  # If gosu isn't available for some reason, make a best-effort to avoid leaving
  # unreadable root-owned files behind.
  umask 002
fi

echo "[backend_init] ensuring Laravel project exists in /var/www/backend" >&2

# If the bind-mounted directory is non-empty but doesn't contain a Laravel app,
# composer create-project will fail.
if [ ! -f artisan ]; then
  if [ -e .env ] || [ -e composer.json ] || [ -d vendor ]; then
    echo "[backend_init] artisan missing but project files exist; continuing" >&2
  else
    if [ "$(ls -A 2>/dev/null | wc -l | tr -d ' ')" != "0" ]; then
      echo "[backend_init] ERROR: /var/www/backend is not empty but no Laravel project was found." >&2
      echo "[backend_init] If this is due to permission issues, run on the host:" >&2
      echo "[backend_init]   sudo chown -R \"$USER\":\"$USER\" backend" >&2
      echo "[backend_init] or delete the directory:" >&2
      echo "[backend_init]   sudo rm -rf backend" >&2
      exit 1
    fi

    echo "[backend_init] scaffolding Laravel 11 into /var/www/backend" >&2
    composer create-project laravel/laravel:^11.0 .
  fi
fi

if [ ! -f vendor/autoload.php ]; then
  echo "[backend_init] installing composer dependencies" >&2
  composer install --no-interaction
fi

if [ ! -f .env ]; then
  echo "[backend_init] creating .env from .env.example" >&2
  cp .env.example .env
fi

fix_env_perms

upsert_env_kv() {
  local key="$1"
  local value="$2"
  local file="${3:-.env}"

  local tmp
  # Create tmp file in the same directory to avoid cross-filesystem rename issues on bind mounts.
  tmp="$(mktemp ./.env.tmp.XXXXXX)"

  awk -v k="$key" -v v="$value" '
    BEGIN { done = 0 }
    $0 ~ ("^" k "=") {
      if (!done) {
        print k "=" v
        done = 1
      }
      next
    }
    { print }
    END {
      if (!done) {
        print k "=" v
      }
    }
  ' "$file" > "$tmp"

  mv "$tmp" "$file"
}

# Sync runtime env to .env so artisan + app are consistent.
{
  echo "[backend_init] syncing runtime env to .env" >&2

  APP_ENV_EFFECTIVE="${APP_ENV:-local}"
  APP_DEBUG_EFFECTIVE="${APP_DEBUG:-true}"
  APP_URL_EFFECTIVE="${APP_URL:-http://localhost}"

  DB_CONNECTION_EFFECTIVE="${DB_CONNECTION:-mysql}"
  DB_HOST_EFFECTIVE="${DB_HOST:-db}"
  DB_PORT_EFFECTIVE="${DB_PORT:-3306}"
  DB_DATABASE_EFFECTIVE="${DB_DATABASE:-backend}"
  DB_USERNAME_EFFECTIVE="${DB_USERNAME:-backend}"
  DB_PASSWORD_EFFECTIVE="${DB_PASSWORD:-backend}"

  if [ "${DB_CONNECTION_EFFECTIVE}" = "pgsql" ] && { [ -z "${DB_PORT:-}" ] || [ "${DB_PORT_EFFECTIVE}" = "3306" ]; }; then
    DB_PORT_EFFECTIVE="5432"
  fi

  REDIS_CLIENT_EFFECTIVE="${REDIS_CLIENT:-phpredis}"
  REDIS_HOST_EFFECTIVE="${REDIS_HOST:-redis}"
  REDIS_PORT_EFFECTIVE="${REDIS_PORT:-6379}"

  QUEUE_CONNECTION_EFFECTIVE="${QUEUE_CONNECTION:-database}"
  SESSION_DRIVER_EFFECTIVE="${SESSION_DRIVER:-file}"
  CACHE_STORE_EFFECTIVE="${CACHE_STORE:-file}"

  if is_production_env; then
    if [ -z "${QUEUE_CONNECTION:-}" ] || [ "${QUEUE_CONNECTION}" = "database" ]; then
      QUEUE_CONNECTION_EFFECTIVE="redis"
    fi

    if [ -z "${SESSION_DRIVER:-}" ] || [ "${SESSION_DRIVER}" = "file" ]; then
      SESSION_DRIVER_EFFECTIVE="redis"
    fi

    if [ -z "${CACHE_STORE:-}" ] || [ "${CACHE_STORE}" = "file" ]; then
      CACHE_STORE_EFFECTIVE="redis"
    fi
  fi

  upsert_env_kv APP_ENV "$APP_ENV_EFFECTIVE"
  upsert_env_kv APP_DEBUG "$APP_DEBUG_EFFECTIVE"
  upsert_env_kv APP_URL "$APP_URL_EFFECTIVE"

  upsert_env_kv DB_CONNECTION "$DB_CONNECTION_EFFECTIVE"
  upsert_env_kv DB_HOST "$DB_HOST_EFFECTIVE"
  upsert_env_kv DB_PORT "$DB_PORT_EFFECTIVE"
  upsert_env_kv DB_DATABASE "$DB_DATABASE_EFFECTIVE"
  upsert_env_kv DB_USERNAME "$DB_USERNAME_EFFECTIVE"
  upsert_env_kv DB_PASSWORD "$DB_PASSWORD_EFFECTIVE"

  upsert_env_kv REDIS_CLIENT "$REDIS_CLIENT_EFFECTIVE"
  upsert_env_kv REDIS_HOST "$REDIS_HOST_EFFECTIVE"
  upsert_env_kv REDIS_PORT "$REDIS_PORT_EFFECTIVE"

  upsert_env_kv QUEUE_CONNECTION "$QUEUE_CONNECTION_EFFECTIVE"
  upsert_env_kv SESSION_DRIVER "$SESSION_DRIVER_EFFECTIVE"
  upsert_env_kv CACHE_STORE "$CACHE_STORE_EFFECTIVE"

  export DB_CONNECTION="$DB_CONNECTION_EFFECTIVE"
  export DB_HOST="$DB_HOST_EFFECTIVE"
  export DB_PORT="$DB_PORT_EFFECTIVE"
  export DB_DATABASE="$DB_DATABASE_EFFECTIVE"
  export DB_USERNAME="$DB_USERNAME_EFFECTIVE"
  export DB_PASSWORD="$DB_PASSWORD_EFFECTIVE"

  export REDIS_CLIENT="$REDIS_CLIENT_EFFECTIVE"
  export REDIS_HOST="$REDIS_HOST_EFFECTIVE"
  export REDIS_PORT="$REDIS_PORT_EFFECTIVE"

  export QUEUE_CONNECTION="$QUEUE_CONNECTION_EFFECTIVE"
  export SESSION_DRIVER="$SESSION_DRIVER_EFFECTIVE"
  export CACHE_STORE="$CACHE_STORE_EFFECTIVE"

  fix_env_perms
}

rm -f bootstrap/cache/config.php bootstrap/cache/routes*.php bootstrap/cache/events.php || true

mkdir -p storage/framework/{cache,data,sessions,views} storage/logs bootstrap/cache
chown -R "${DOCKER_UID:-1000}":"${DOCKER_GID:-1000}" storage bootstrap/cache || true
chmod -R ug+rwX storage bootstrap/cache || true

# Ensure APP_KEY exists (and only appears once).
normalize_app_key

if ! grep -q "^APP_KEY=" .env || [ "$(grep -E "^APP_KEY=" .env | head -n 1 | cut -d= -f2- | tr -d '[:space:]')" = "" ]; then
  echo "[backend_init] generating APP_KEY" >&2

  # We do not rely exclusively on `php artisan key:generate` because on some
  # bind-mounted setups it can report success without persisting the change.
  APP_KEY_FORCED="$(php -r 'echo "base64:".base64_encode(random_bytes(32));')"
  upsert_env_kv APP_KEY "${APP_KEY_FORCED}"
  normalize_app_key

  # Also export it for subsequent artisan commands in this init process.
  export APP_KEY="${APP_KEY_FORCED}"
fi

# Ensure tests have an APP_KEY too (php artisan test loads .env.testing if present).
# Keep it in sync with .env to avoid MissingAppKeyException.
if [ -f .env ]; then
  APP_KEY_VAL="$(grep -E '^APP_KEY=' .env | tail -n 1 | cut -d= -f2-)"
  if [ ! -f .env.testing ]; then
    cp .env .env.testing
  fi
  upsert_env_kv APP_ENV "testing" .env.testing
  upsert_env_kv APP_DEBUG "true" .env.testing
  upsert_env_kv APP_KEY "${APP_KEY_VAL}" .env.testing
  upsert_env_kv DB_CONNECTION "${DB_CONNECTION_EFFECTIVE:-mysql}" .env.testing
  upsert_env_kv DB_HOST "${DB_HOST_EFFECTIVE:-db}" .env.testing
  upsert_env_kv DB_PORT "${DB_PORT_EFFECTIVE:-3306}" .env.testing
  upsert_env_kv DB_DATABASE "${DB_DATABASE_EFFECTIVE:-backend}" .env.testing
  upsert_env_kv DB_USERNAME "${DB_USERNAME_EFFECTIVE:-backend}" .env.testing
  upsert_env_kv DB_PASSWORD "${DB_PASSWORD_EFFECTIVE:-backend}" .env.testing
  upsert_env_kv REDIS_CLIENT "${REDIS_CLIENT_EFFECTIVE:-phpredis}" .env.testing
  upsert_env_kv REDIS_HOST "${REDIS_HOST_EFFECTIVE:-redis}" .env.testing
  upsert_env_kv REDIS_PORT "${REDIS_PORT_EFFECTIVE:-6379}" .env.testing
  fix_env_perms
fi

# Install Breeze (Blade) once
if [ ! -f routes/auth.php ]; then
  echo "[backend_init] installing Laravel Breeze (Blade)" >&2
  composer require laravel/breeze --dev --no-interaction
  php artisan breeze:install blade --no-interaction
fi

# Apply repo-managed overrides (controllers, models, routes, etc.)
# We use tar to avoid requiring rsync in the container.
#
# Cleanup for legacy/accidental file placements from earlier iterations.
# If a previous boot wrote the API controller into the non-API path, it will
# conflict at runtime with the correct Api\ProjectController.
if [ -f app/Http/Controllers/ProjectController.php ] && grep -Eqi "namespace[[:space:]]+App\\Http\\Controllers\\Api" app/Http/Controllers/ProjectController.php; then
  echo "[backend_init] removing legacy misplaced Api\\ProjectController" >&2
  rm -f app/Http/Controllers/ProjectController.php
fi

echo "[backend_init] applying backend overrides" >&2
mkdir -p /var/www/backend

tar -C /bootstrap/overrides -cf - . | tar -C /var/www/backend -xf -

# The overrides directory is the source of truth for API controllers.
# Copy them explicitly to avoid any "partial copy" edge cases.
mkdir -p app/Http/Controllers/Api
for src in /bootstrap/overrides/app/Http/Controllers/Api/*.php; do
  if [ -f "$src" ]; then
    cp -f "$src" "app/Http/Controllers/Api/$(basename "$src")"
  fi
done

# Also force the web ProjectController override, as earlier iterations may have
# accidentally written an Api\\ProjectController into the web path.
if [ -f /bootstrap/overrides/app/Http/Controllers/ProjectController.php ]; then
  cp -f /bootstrap/overrides/app/Http/Controllers/ProjectController.php app/Http/Controllers/ProjectController.php
fi

# Some earlier bootstraps ended up with an Api\ProjectController without index().
# Ensure the internal API listing endpoint exists by copying the override.
if [ -f app/Http/Controllers/Api/ProjectController.php ] && ! grep -q "function index" app/Http/Controllers/Api/ProjectController.php; then
  echo "[backend_init] copying Api\\ProjectController override (missing index())" >&2
  cp -f /bootstrap/overrides/app/Http/Controllers/Api/ProjectController.php app/Http/Controllers/Api/ProjectController.php
fi

# Guard against accidental "- >" sequences that break PHP parsing in Blade.
if command -v find >/dev/null 2>&1 && command -v sed >/dev/null 2>&1; then
  find resources/views -type f -name "*.blade.php" -print0 2>/dev/null | xargs -0 sed -i -E 's/-[[:space:]]*>/->/g' 2>/dev/null || true
fi

rm -f storage/framework/views/*.php 2>/dev/null || true
php artisan view:clear || true

# Sync repo-specific vars to .env (source of truth is docker-compose env).
# This avoids stale values sticking around across backend_init runs.
upsert_env_kv ADMIN_EMAILS "${ADMIN_EMAILS:-admin@example.com}"
upsert_env_kv ADMIN_PASSWORD "${ADMIN_PASSWORD:-password}"
upsert_env_kv INTERNAL_API_SECRET "${INTERNAL_API_SECRET:-change-me}"
upsert_env_kv VIDEO_WORKER_BASE_URL "${VIDEO_WORKER_BASE_URL:-}"
upsert_env_kv VIDEO_WORKER_API_KEY "${VIDEO_WORKER_API_KEY:-}"
upsert_env_kv VIDEO_WORKER_CALLBACK_SECRET "${VIDEO_WORKER_CALLBACK_SECRET:-change-me-too}"
upsert_env_kv WORKER_CALLBACK_URL "${WORKER_CALLBACK_URL:-http://backend:8000/api/worker/callback}"
upsert_env_kv SHARED_STORAGE_ROOT "${SHARED_STORAGE_ROOT:-/shared}"

fix_env_perms

# Wait for DB
if [ "${DB_CONNECTION:-}" = "mysql" ]; then
  echo "[backend_init] waiting for MySQL" >&2
  php -r '
    $host = getenv("DB_HOST");
    $port = getenv("DB_PORT") ?: "3306";
    $db = getenv("DB_DATABASE");
    $user = getenv("DB_USERNAME");
    $pass = getenv("DB_PASSWORD");
    $dsn = "mysql:host={$host};port={$port};dbname={$db}";
    $started = time();
    while (true) {
      try {
        new PDO($dsn, $user, $pass);
        break;
      } catch (Throwable $e) {
        if (time() - $started > 120) {
          fwrite(STDERR, "mysql_timeout: {$e->getMessage()}\n");
          exit(1);
        }
        sleep(2);
      }
    }
  ';
fi

if [ "${DB_CONNECTION:-}" = "pgsql" ]; then
  echo "[backend_init] waiting for Postgres" >&2
  php -r '
    $host = getenv("DB_HOST");
    $port = getenv("DB_PORT") ?: "5432";
    $db = getenv("DB_DATABASE");
    $user = getenv("DB_USERNAME");
    $pass = getenv("DB_PASSWORD");
    $dsn = "pgsql:host={$host};port={$port};dbname={$db}";
    $started = time();
    while (true) {
      try {
        new PDO($dsn, $user, $pass);
        break;
      } catch (Throwable $e) {
        if (time() - $started > 120) {
          fwrite(STDERR, "pgsql_timeout: {$e->getMessage()}\n");
          exit(1);
        }
        sleep(2);
      }
    }
  ';
fi

# NPM assets (Tailwind + Vite)
if [ ! -f public/build/manifest.json ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "[backend_init] building frontend assets" >&2
    npm install
    npm run build
  fi
fi

echo "[backend_init] running migrations" >&2
php artisan migrate --force

echo "[backend_init] seeding" >&2
php artisan db:seed --force

# Final permission fix in case any step created root-owned files.
if [ "$(id -u)" = "0" ]; then
  chown -R "${DOCKER_UID:-1000}":"${DOCKER_GID:-1000}" /var/www/backend || true
  chmod -R ug+rwX /var/www/backend || true
fi

echo "[backend_init] done" >&2
