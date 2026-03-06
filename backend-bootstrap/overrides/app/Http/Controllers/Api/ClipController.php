<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Models\Clip;
use App\Support\SharedStorage;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

class ClipController
{
    public function index(Request $request): JsonResponse
    {
        $clips = Clip::query()
            ->with(['project'])
            ->orderByDesc('created_at')
            ->limit(200)
            ->get();

        return response()->json([
            'data' => $clips->map(static function (Clip $clip): array {
                $start = $clip->start_seconds;
                $end = $clip->end_seconds;
                $duration = null;
                if ($start !== null && $end !== null) {
                    $duration = max(0, (float) $end - (float) $start);
                }

                return [
                    'id' => (string) $clip->id,
                    'project_id' => (string) $clip->project_id,
                    'project_name' => $clip->project?->name,
                    'status' => $clip->status->value,
                    'start_seconds' => $clip->start_seconds,
                    'end_seconds' => $clip->end_seconds,
                    'duration_seconds' => $duration,
                    'score' => $clip->score,
                    'reason' => $clip->reason,
                    'title' => $clip->title,
                    'title_candidates' => $clip->title_candidates,
                    'quality_summary' => $clip->quality_summary,
                    'video_path' => $clip->video_path,
                    'subtitles_ass_path' => $clip->subtitles_ass_path,
                    'subtitles_srt_path' => $clip->subtitles_srt_path,
                    'created_at' => $clip->created_at?->toISOString(),
                    'updated_at' => $clip->updated_at?->toISOString(),
                ];
            })->values(),
        ]);
    }

    public function show(Request $request, Clip $clip): JsonResponse
    {
        $clip->load([
            'project',
            'pipelineEvents' => static fn ($q) => $q->latest()->limit(200),
        ]);

        $start = $clip->start_seconds;
        $end = $clip->end_seconds;
        $duration = null;
        if ($start !== null && $end !== null) {
            $duration = max(0, (float) $end - (float) $start);
        }

        return response()->json([
            'id' => (string) $clip->id,
            'project' => $clip->project ? [
                'id' => (string) $clip->project->id,
                'name' => $clip->project->name,
            ] : null,
            'status' => $clip->status->value,
            'start_seconds' => $clip->start_seconds,
            'end_seconds' => $clip->end_seconds,
            'duration_seconds' => $duration,
            'score' => $clip->score,
            'reason' => $clip->reason,
            'title' => $clip->title,
            'title_candidates' => $clip->title_candidates,
            'quality_summary' => $clip->quality_summary,

            'tiktok_caption' => $clip->tiktok_caption,
            'tiktok_account_id' => $clip->tiktok_account_id ? (string) $clip->tiktok_account_id : null,
            'tiktok_publish_job_id' => $clip->tiktok_publish_job_id,
            'tiktok_publish_status' => $clip->tiktok_publish_status,
            'tiktok_publish_error' => $clip->tiktok_publish_error,
            'tiktok_published_at' => $clip->tiktok_published_at?->toISOString(),

            'video_path' => $clip->video_path,
            'subtitles_ass_path' => $clip->subtitles_ass_path,
            'subtitles_srt_path' => $clip->subtitles_srt_path,
            'events' => $clip->pipelineEvents->map(static function (\App\Models\PipelineEvent $event): array {
                return [
                    'id' => (string) $event->id,
                    'type' => $event->type,
                    'message' => $event->message,
                    'payload' => $event->payload,
                    'created_at' => $event->created_at?->toISOString(),
                ];
            })->values(),
            'created_at' => $clip->created_at?->toISOString(),
            'updated_at' => $clip->updated_at?->toISOString(),
        ]);
    }

    public function update(Request $request, Clip $clip): JsonResponse
    {
        $data = $request->validate([
            'tiktok_caption' => ['sometimes', 'nullable', 'string', 'max:2200'],
            'title' => ['sometimes', 'nullable', 'string', 'max:255'],
            'hashtags' => ['sometimes', 'nullable', 'array', 'max:10'],
            'hashtags.*' => ['string', 'max:50'],
        ]);

        $updates = [];

        if (array_key_exists('tiktok_caption', $data)) {
            $updates['tiktok_caption'] = $data['tiktok_caption'];
        }

        if (array_key_exists('title', $data)) {
            $updates['title'] = $data['title'];
        }

        if (array_key_exists('hashtags', $data)) {
            $existingCandidates = is_array($clip->title_candidates) ? $clip->title_candidates : [];
            $existingCandidates['hashtags'] = $data['hashtags'] ?? [];
            $updates['title_candidates'] = $existingCandidates;
        }

        if (!empty($updates)) {
            $clip->forceFill($updates)->save();
        }

        return $this->show($request, $clip->refresh());
    }

    public function destroy(Request $request, Clip $clip): Response
    {
        SharedStorage::deleteFile($clip->video_path);
        SharedStorage::deleteFile($clip->subtitles_ass_path);
        SharedStorage::deleteFile($clip->subtitles_srt_path);

        $clip->delete();

        return response()->noContent();
    }
}