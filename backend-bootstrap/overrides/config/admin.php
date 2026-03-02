<?php

declare(strict_types=1);

return [
    'emails' => array_values(array_filter(array_map(
        static fn (string $email) => trim($email),
        explode(',', (string) env('ADMIN_EMAILS', '')),
    ))),

    'password' => (string) env('ADMIN_PASSWORD', 'password'),

    'internal_api_secret' => (string) env('INTERNAL_API_SECRET', ''),

    // Path inside the backend container where worker artifacts are mounted.
    // Used to safely serve clip files in the admin UI.
    'shared_storage_root' => (string) env('SHARED_STORAGE_ROOT', '/shared'),

    'video_worker_base_url' => (string) env('VIDEO_WORKER_BASE_URL', ''),
    'video_worker_api_key' => (string) env('VIDEO_WORKER_API_KEY', ''),
    'video_worker_callback_secret' => (string) env('VIDEO_WORKER_CALLBACK_SECRET', ''),

    // tiktok-bot integration (optional)
    'tiktok_bot_base_url' => (string) env('TIKTOK_BOT_BASE_URL', ''),

    // Header shared with tiktok-bot: X-Internal-Secret
    // We reuse the same INTERNAL_API_SECRET used for the internal API.
    'tiktok_bot_internal_secret' => (string) env('INTERNAL_API_SECRET', ''),

    'worker_callback_url' => (string) env(
        'WORKER_CALLBACK_URL',
        rtrim((string) env('APP_URL', ''), '/').'/api/worker/callback',
    ),
];