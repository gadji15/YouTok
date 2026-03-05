<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Enums\ProjectStatus;
use App\Jobs\SubmitVideoWorkerJob;
use App\Models\PipelineEvent;
use App\Models\Project;
use App\Services\VideoWorkerClient;
use App\Support\SharedStorage;
use App\Support\Youtube;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

class ProjectController
{
    public function index(Request $request): JsonResponse
    {
        $projects = Project::query()
            ->orderByDesc('updated_at')
            ->limit(200)
            ->get();

        return response()->json([
            'data' => $projects->map(static fn (Project $project): array => [
                'id' => (string) $project->id,
                'name' => $project->name,
                'youtube_url' => $project->youtube_url,
                'status' => $project->status->value,
                'stage' => $project->stage,
                'progress_percent' => $project->progress_percent,
                'updated_at' => $project->updated_at?->toISOString(),
                'created_at' => $project->created_at?->toISOString(),
            ])->values(),
        ]);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'youtube_url' => [
                'required',
                'url',
                'max:2048',
                static function (string $attribute, mixed $value, \Closure $fail): void {
                    if (!is_string($value) || !Youtube::isValidUrl($value)) {
                        $fail('The YouTube URL must be a youtube.com or youtu.be link.');
                    }
                },
            ],

            // Rendering options
            'language' => ['sometimes', 'nullable', 'in:fr,en'],
            'subtitles_enabled' => ['sometimes', 'boolean'],
            'clip_min_seconds' => ['sometimes', 'integer', 'min:15', 'max:60'],
            'clip_max_seconds' => ['sometimes', 'integer', 'min:15', 'max:60', 'gte:clip_min_seconds'],
            'subtitle_template' => ['sometimes', 'nullable', 'string', 'max:32'],
            'segmentation_mode' => ['sometimes', 'nullable', 'in:viral,chapters'],
            'originality_mode' => ['sometimes', 'nullable', 'in:none,voiceover'],
            'output_aspect' => ['sometimes', 'nullable', 'in:vertical,source'],
        ]);

        $clipMin = (int) ($request->input('clip_min_seconds', 15));
        $clipMax = (int) ($request->input('clip_max_seconds', 60));

        // Use request accessors for optional fields to avoid edge cases where
        // validated payload may omit optional keys (e.g. false boolean values).
        $project = Project::query()->create([
            'name' => $data['name'],
            'youtube_url' => $data['youtube_url'],
            'language' => $request->input('language'),
            'subtitles_enabled' => $request->boolean('subtitles_enabled', true),
            'clip_min_seconds' => $clipMin,
            'clip_max_seconds' => $clipMax,
            'subtitle_template' => $request->input('subtitle_template'),
            'segmentation_mode' => $request->input('segmentation_mode') ?? 'viral',
            'originality_mode' => $request->input('originality_mode') ?? 'none',
            'output_aspect' => $request->input('output_aspect') ?? 'vertical',
            'status' => ProjectStatus::queued,
        ]);

        PipelineEvent::log('project.created', payload: ['source' => 'api'], project: $project);
        SubmitVideoWorkerJob::dispatch((string) $project->id)->afterCommit();

        return response()->json([
            'id' => (string) $project->id,
            'status' => $project->status->value,
        ], 201);
    }

    public function show(Request $request, Project $project): JsonResponse
    {
        $clipsQuery = $project->segmentation_mode === 'chapters'
            ? fn ($query) => $query->orderBy('start_seconds')->orderBy('created_at')
            : static fn ($query) => $query->orderByDesc('score')->orderByDesc('created_at');

        $project->load([
            'clips' => $clipsQuery,
            'pipelineEvents' => static fn ($query) => $query->latest()->limit(200),
        ]);

        return response()->json([
            'id' => (string) $project->id,
            'name' => $project->name,
            'youtube_url' => $project->youtube_url,
            'status' => $project->status->value,
            'stage' => $project->stage,
            'progress_percent' => $project->progress_percent,
            'last_log_message' => $project->last_log_message,
            'error' => $project->error,

            'options' => [
                'language' => $project->language,
                'subtitles_enabled' => (bool) $project->subtitles_enabled,
                'clip_min_seconds' => (int) $project->clip_min_seconds,
                'clip_max_seconds' => (int) $project->clip_max_seconds,
                'subtitle_template' => $project->subtitle_template,
                'segmentation_mode' => $project->segmentation_mode ?? 'viral',
                'originality_mode' => $project->originality_mode ?? 'none',
                'output_aspect' => $project->output_aspect ?? 'vertical',
            ],

            'artifacts' => [
                'source_video_path' => $project->source_video_path,
                'audio_path' => $project->audio_path,
                'transcript_json_path' => $project->transcript_json_path,
                'subtitles_srt_path' => $project->subtitles_srt_path,
                'clips_json_path' => $project->clips_json_path,
                'words_json_path' => $project->words_json_path,
                'segments_json_path' => $project->segments_json_path,
                'source_metadata_json_path' => $project->source_metadata_json_path,
                'source_thumbnail_path' => $project->source_thumbnail_path,
            ],

            'clips' => $project->clips->map(static function (\App\Models\Clip $clip): array {
                $start = $clip->start_seconds;
                $end = $clip->end_seconds;
                $duration = null;
                if ($start !== null && $end !== null) {
                    $duration = max(0, (float) $end - (float) $start);
                }

                return [
                    'id' => (string) $clip->id,
                    'external_id' => $clip->external_id,
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
                ];
            })->values(),

            'events' => $project->pipelineEvents->map(static function (\App\Models\PipelineEvent $event): array {
                return [
                    'id' => (string) $event->id,
                    'type' => $event->type,
                    'message' => $event->message,
                    'payload' => $event->payload,
                    'created_at' => $event->created_at?->toISOString(),
                ];
            })->values(),

            'created_at' => $project->created_at?->toISOString(),
            'updated_at' => $project->updated_at?->toISOString(),
        ]);
    }

    public function destroy(Request $request, Project $project, VideoWorkerClient $videoWorker): Response
    {
        $project->load(['clips']);

        // Best-effort cancellation to avoid leaving orphan jobs in the worker queue.
        if (is_string($project->worker_job_id) && $project->worker_job_id !== '') {
            $videoWorker->cancelJob($project->worker_job_id);
        }

        SharedStorage::deleteFile($project->source_video_path);
        SharedStorage::deleteFile($project->audio_path);
        SharedStorage::deleteFile($project->transcript_json_path);
        SharedStorage::deleteFile($project->subtitles_srt_path);
        SharedStorage::deleteFile($project->clips_json_path);
        SharedStorage::deleteFile($project->words_json_path);
        SharedStorage::deleteFile($project->segments_json_path);
        SharedStorage::deleteFile($project->source_metadata_json_path);
        SharedStorage::deleteFile($project->source_thumbnail_path);

        foreach ($project->clips as $clip) {
            SharedStorage::deleteFile($clip->video_path);
            SharedStorage::deleteFile($clip->subtitles_ass_path);
            SharedStorage::deleteFile($clip->subtitles_srt_path);
        }

        $project->delete();

        return response()->noContent();
    }
}