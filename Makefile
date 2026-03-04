.PHONY: up up-video-worker up-tiktok-bot down logs backend-shell migrate seed-admin queue-logs video-worker-test

up:
	docker compose up -d --build

up-video-worker:
	docker compose --profile video-worker up -d --build

up-tiktok-bot:
	docker compose --profile tiktok-bot up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

backend-shell:
	docker compose exec backend bash

migrate:
	docker compose exec backend php artisan migrate --force

seed-admin:
	# Re-seed the admin user (normally done automatically by backend_init)
	docker compose exec backend php artisan db:seed --class=Database\\Seeders\\AdminUserSeeder --force

queue-logs:
	docker compose logs -f --tail=200 queue

video-worker-test:
	# Run python unit tests inside the video-worker image (no host Python env needed)
	docker compose --profile video-worker run --rm video-worker-worker python -m pytest -q
	