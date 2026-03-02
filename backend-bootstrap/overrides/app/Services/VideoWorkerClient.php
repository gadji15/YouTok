<?php

declare(strict_types=1);

namespace App\Services;

use App\Models\Project;
use Illuminate\Http\Client\PendingRequest;
use Illuminate\Support\Facades\Http;

class VideoWorkerClient
{
    public function createJob(Project $project): ?string
    {
        $baseUrl = (string) config('admin.video_worker_base_url', '');
        if ($baseUrl === '') {
            return null;
        }

        $callbackUrl = (string) config('admin.worker_callback_url');
        $callbackSecret = (string) config('admin.video_worker_callback_secret');

        $request = Http::timeout(30);

        $apiKey = (string) config('admin.video_worker_api_key', '');
        if ($apiKey !== '') {
            $request = $request->withToken($apiKey);
        }

        $response = $this->post(
            request: $request,
            url: rtrim($baseUrl, '/').'/jobs',
            payload: [
                'project_id' => (string) $project->id,
                'youtube_url' => $project->youtube_url,
                'callback_url' => $callbackUrl,
                'callback_secret' => $callbackSecret,

                // Options (stored on Project so retries are deterministic)
                'language' => $project->language,
                'subtitles_enabled' => (bool) ($project->subtitles_enabled ?? true),
                'clip_min_seconds' => (int) ($project->clip_min_seconds ?? 60),
                'clip_max_seconds' => (int) ($project->clip_max_seconds ?? 180),
                'subtitle_template' => $project->subtitle_template,
            ],
        );

        $jobId = $response->json('job_id');
        if (!is_string($jobId) || $jobId === '') {
            throw new \RuntimeException('video-worker did not return job_id');
        }

        return $jobId;
    }

    private function post(PendingRequest $request, string $url, array $payload)
    {
        $response = $request->post($url, $payload);
        $response->throw();
        return $response;
    }
}
