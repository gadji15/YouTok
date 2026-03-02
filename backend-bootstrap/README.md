# backend-bootstrap

This repo bootstraps a Laravel backend into `./backend/` at runtime.

- `docker compose up` runs an init container that:
  - scaffolds Laravel 11 into `./backend/` if missing
  - installs Laravel Breeze (Blade) + Tailwind
  - copies repo-managed overrides from `backend-bootstrap/overrides/`
  - runs migrations + seeds an admin user

See the root-level instructions in the main task response for verification steps.
