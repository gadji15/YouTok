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

        $payload = [
            'project_id' => (string) $project->id,
            'callback_url' => $callbackUrl,
            'callback_secret' => $callbackSecret,

            // Source (Part 2): YouTube URL OR local file path.
            'youtube_url' => $project->youtube_url,
            'local_video_path' => $project->local_video_path,

            // Options (stored on Project so retries are deterministic)
            'language' => $project->language,
            'subtitles_enabled' => (bool) ($project->subtitles_enabled ?? true),
            'clip_min_seconds' => (int) ($project->clip_min_seconds ?? 15),
            'clip_max_seconds' => (int) ($project->clip_max_seconds ?? 60),
            'subtitle_template' => $project->subtitle_template,
            'segmentation_mode' => $project->segmentation_mode ?? 'viral',
            'originality_mode' => $project->originality_mode ?? 'none',
            'output_aspect' => $project->output_aspect ?? 'vertical',
        ];

        // Enforce one-of source to satisfy the video-worker API contract.
        if (is_string($payload['local_video_path']) && $payload['local_video_path'] !== '') {
            $payload['youtube_url'] = null;
        } else {
            $payload['local_video_path'] = null;
        }

        $response = $this->post(
            request: $request,
            url: rtrim($baseUrl, '/').'/jobs',
            payload: $payload,
        );

        $jobId = $response->json('job_id');
        if (!is_string($jobId) || $jobId === '') {
            throw new \RuntimeException('video-worker did not return job_id');
        }

        return $jobId;
    }

    public function cancelJob(string $jobId): void
    {
        $baseUrl = (string) config('admin.video_worker_base_url', '');
        if ($baseUrl === '' || $jobId === '') {
            return;
        }

        $request = Http::timeout(10);

        $apiKey = (string) config('admin.video_worker_api_key', '');
        if ($apiKey !== '') {
            $request = $request->withToken($apiKey);
        }

        // Best-effort: if the job already finished or the worker is down, we don't block deletion.
        $request->delete(rtrim($baseUrl, '/').'/jobs/'.urlencode($jobId));
    }

    private function post(PendingRequest $request, string $url, array $payload)
    {
        $response = $request->post($url, $payload);
        $response->throw();
        return $response;
    }
}