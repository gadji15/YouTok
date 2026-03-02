<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Enums\TikTokAccountStatus;
use App\Models\Clip;
use App\Models\PipelineEvent;
use App\Models\TikTokAccount;
use App\Services\TikTokBotClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;

class ClipPublishController extends Controller
{
    public function publish(Request $request, Clip $clip, TikTokBotClient $client): RedirectResponse
    {
        $this->authorize('view', $clip);

        $data = $request->validate([
            'tiktok_account_id' => ['required', 'uuid'],
            'caption' => ['required', 'string', 'max:2200'],
        ]);

        if (!$clip->video_path) {
            return back()->with('status', 'Cannot publish: clip has no rendered video.');
        }

        $account = TikTokAccount::query()->findOrFail($data['tiktok_account_id']);
        if ($account->status !== TikTokAccountStatus::active) {
            return back()->with('status', 'TikTok account is not active.');
        }

        $baseUrl = (string) config('admin.tiktok_bot_base_url', '');
        if ($baseUrl === '') {
            return back()->with('status', 'Cannot publish: TIKTOK_BOT_BASE_URL is not configured.');
        }

        try {
            $resp = $client->publishClip(
                clipPath: (string) $clip->video_path,
                caption: $data['caption'],
                accountId: (string) $account->id,
            );

            $jobId = $resp['job_id'] ?? null;
            if (!is_string($jobId) || $jobId === '') {
                throw new \RuntimeException('tiktok-bot did not return job_id');
            }

            $clip->forceFill([
                'tiktok_account_id' => (string) $account->id,
                'tiktok_caption' => $data['caption'],
                'tiktok_publish_job_id' => $jobId,
                'tiktok_publish_status' => 'queued',
                'tiktok_publish_error' => null,
                'tiktok_published_at' => null,
            ])->save();

            PipelineEvent::log(
                type: 'tiktok.publish.queued',
                payload: ['job_id' => $jobId],
                project: $clip->project,
                clip: $clip,
            );

            return back()->with('status', 'Publish job queued.');
        } catch (\Throwable $e) {
            $clip->forceFill([
                'tiktok_publish_status' => 'failed',
                'tiktok_publish_error' => $e->getMessage(),
            ])->save();

            PipelineEvent::log(
                type: 'tiktok.publish.failed',
                message: $e->getMessage(),
                payload: ['exception' => $e::class],
                project: $clip->project,
                clip: $clip,
            );

            Log::error('tiktok.publish.failed', [
                'clip_id' => $clip->id,
                'exception' => $e::class,
                'message' => $e->getMessage(),
            ]);

            return back()->with('status', 'Publish failed: '.$e->getMessage());
        }
    }

    public function status(Request $request, Clip $clip, TikTokBotClient $client): JsonResponse
    {
        $this->authorize('view', $clip);

        $jobId = (string) ($clip->tiktok_publish_job_id ?? '');
        if ($jobId === '') {
            return response()->json([
                'status' => 'not_started',
            ]);
        }

        try {
            $job = $client->getJob($jobId);

            $state = (string) ($job['status'] ?? 'unknown');
            $failedReason = $job['failedReason'] ?? null;

            $updates = [
                'tiktok_publish_status' => $state,
            ];

            if ($state === 'completed') {
                $updates['tiktok_published_at'] = now();
                $updates['tiktok_publish_error'] = null;
            }

            if ($state === 'failed') {
                $updates['tiktok_publish_error'] = is_string($failedReason) ? $failedReason : 'failed';
            }

            $clip->forceFill($updates)->save();

            return response()->json([
                'status' => $clip->tiktok_publish_status,
                'job_id' => $clip->tiktok_publish_job_id,
                'error' => $clip->tiktok_publish_error,
                'published_at' => $clip->tiktok_published_at?->toISOString(),
                'job' => $job,
            ]);
        } catch (\Throwable $e) {
            return response()->json([
                'status' => $clip->tiktok_publish_status,
                'job_id' => $clip->tiktok_publish_job_id,
                'error' => $e->getMessage(),
            ], 502);
        }
    }
}