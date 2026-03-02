<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Models\Clip;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

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
}
