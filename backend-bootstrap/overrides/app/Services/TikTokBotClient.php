<?php

declare(strict_types=1);

namespace App\Services;

use Illuminate\Http\Client\PendingRequest;
use Illuminate\Support\Facades\Http;

class TikTokBotClient
{
    public function publishClip(string $clipPath, string $caption, string $accountId): array
    {
        $baseUrl = (string) config('admin.tiktok_bot_base_url', '');
        if ($baseUrl === '') {
            throw new \RuntimeException('TIKTOK_BOT_BASE_URL is not set');
        }

        $request = $this->request();

        $response = $request->post(rtrim($baseUrl, '/').'/publish', [
            'clip_path' => $clipPath,
            'caption' => $caption,
            'account_id' => $accountId,
        ]);

        $response->throw();

        /** @var array $data */
        $data = $response->json();

        return $data;
    }

    public function getJob(string $jobId): array
    {
        $baseUrl = (string) config('admin.tiktok_bot_base_url', '');
        if ($baseUrl === '') {
            throw new \RuntimeException('TIKTOK_BOT_BASE_URL is not set');
        }

        $request = $this->request();

        $response = $request->get(rtrim($baseUrl, '/').'/jobs/'.$jobId);
        $response->throw();

        /** @var array $data */
        $data = $response->json();

        return $data;
    }

    private function request(): PendingRequest
    {
        $secret = (string) config('admin.tiktok_bot_internal_secret', '');
        if ($secret === '') {
            throw new \RuntimeException('INTERNAL_API_SECRET is not set (required for tiktok-bot calls)');
        }

        return Http::timeout(30)->withHeaders([
            'X-Internal-Secret' => $secret,
            'Accept' => 'application/json',
        ]);
    }
}