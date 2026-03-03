<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Enums\ClipStatus;
use App\Enums\ProjectStatus;
use App\Models\Clip;
use App\Models\PipelineEvent;
use App\Models\Project;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;

class WorkerCallbackController
{
    public function store(Request $request): JsonResponse
    {
        $payload = $request->validate([
            'job_id' => ['required', 'string'],
            'project_id' => ['required', 'uuid'],
            'status' => ['required', 'string'],
            'error' => ['sometimes', 'nullable', 'string'],

            'progress_percent' => ['sometimes', 'nullable', 'integer', 'min:0', 'max:100'],
            'stage' => ['sometimes', 'nullable', 'string', 'max:255'],

            // 'log_message' is the canonical field. 'message' is accepted for backwards compatibility
            // with earlier worker payloads.
            'log_message' => ['sometimes', 'nullable', 'string'],
            'message' => ['sometimes', 'nullable', 'string'],

            'artifacts' => ['sometimes', 'array'],
            'artifacts.source_video_path' => ['sometimes', 'nullable', 'string'],
            'artifacts.audio_path' => ['sometimes', 'nullable', 'string'],
            'artifacts.transcript_json_path' => ['sometimes', 'nullable', 'string'],
            'artifacts.subtitles_srt_path' => ['sometimes', 'nullable', 'string'],
            'artifacts.clips_json_path' => ['sometimes', 'nullable', 'string'],

            'artifacts.clips' => ['sometimes', 'array'],
            'artifacts.clips.*.clip_id' => ['required_with:artifacts.clips', 'string'],
            'artifacts.clips.*.start_seconds' => ['nullable', 'numeric'],
            'artifacts.clips.*.end_seconds' => ['nullable', 'numeric'],
            'artifacts.clips.*.score' => ['nullable', 'numeric'],
            'artifacts.clips.*.reason' => ['nullable', 'string'],
            'artifacts.clips.*.title' => ['nullable', 'string', 'max:255'],
            'artifacts.clips.*.title_candidates' => ['sometimes', 'nullable', 'array'],
            'artifacts.clips.*.title_candidates.provider' => ['sometimes', 'nullable', 'string', 'max:50'],
            'artifacts.clips.*.title_candidates.description' => ['sometimes', 'nullable', 'string', 'max:255'],
            'artifacts.clips.*.title_candidates.hashtags' => ['sometimes', 'nullable', 'array', 'max:10'],
            'artifacts.clips.*.title_candidates.hashtags.*' => ['string', 'max:50'],
            'artifacts.clips.*.title_candidates.candidates' => ['sometimes', 'array', 'max:16'],
            'artifacts.clips.*.title_candidates.candidates.*.title' => ['sometimes', 'string', 'max:255'],
            'artifacts.clips.*.title_candidates.candidates.*.score' => ['sometimes', 'numeric'],
            'artifacts.clips.*.title_candidates.candidates.*.features' => ['sometimes', 'nullable', 'array'],
            'artifacts.clips.*.title_candidates.top3' => ['sometimes', 'array', 'max:3'],
            'artifacts.clips.*.title_candidates.top3.*' => ['string', 'max:255'],
            'artifacts.clips.*.video_path' => ['nullable', 'string'],
            'artifacts.clips.*.subtitles_ass_path' => ['nullable', 'string'],
            'artifacts.clips.*.subtitles_srt_path' => ['nullable', 'string'],
        ]);

        $project = Project::query()->findOrFail($payload['project_id']);

        PipelineEvent::log(
            type: 'worker.callback',
            message: (string) $payload['status'],
            payload: [
                'job_id' => $payload['job_id'],
                'status' => $payload['status'],
                'error' => $payload['error'] ?? null,
                'progress_percent' => $payload['progress_percent'] ?? null,
                'stage' => $payload['stage'] ?? null,
                'message' => $payload['log_message'] ?? $payload['message'] ?? null,
            ],
            project: $project,
        );

        Log::info('worker.callback', [
            'project_id' => $project->id,
            'job_id' => $payload['job_id'],
            'status' => $payload['status'],
            'progress_percent' => $payload['progress_percent'] ?? null,
            'stage' => $payload['stage'] ?? null,
            'message' => $payload['log_message'] ?? $payload['message'] ?? null,
        ]);

        $incomingJobId = (string) $payload['job_id'];
        if ($project->worker_job_id !== null && $project->worker_job_id !== $incomingJobId) {
            PipelineEvent::log(
                type: 'worker.callback.ignored',
                message: 'job_id mismatch',
                payload: [
                    'expected' => $project->worker_job_id,
                    'got' => $incomingJobId,
                ],
                project: $project,
            );

            return response()->json(['ok' => true]);
        }

        $incomingStatus = $this->mapProjectStatus((string) $payload['status']);
        $shouldUpdateStatus = $incomingStatus !== null && $this->shouldUpdateStatus($project->status, $incomingStatus);

        $logMessage = $payload['log_message'] ?? $payload['message'] ?? null;

        // Prevent late/out-of-order non-terminal callbacks from overwriting progress/stage after completion.
        $isTerminal = in_array($project->status, [ProjectStatus::completed, ProjectStatus::failed], true);
        $allowProgressUpdates = !$isTerminal || ($incomingStatus !== null && $incomingStatus === $project->status);

        $updates = [
            'worker_job_id' => $incomingJobId,
            'source_video_path' => data_get($payload, 'artifacts.source_video_path'),
            'audio_path' => data_get($payload, 'artifacts.audio_path'),
            'transcript_json_path' => data_get($payload, 'artifacts.transcript_json_path'),
            'subtitles_srt_path' => data_get($payload, 'artifacts.subtitles_srt_path'),
            'clips_json_path' => data_get($payload, 'artifacts.clips_json_path'),
        ];

        if ($allowProgressUpdates && array_key_exists('progress_percent', $payload)) {
            $updates['progress_percent'] = $payload['progress_percent'];
        }

        if ($allowProgressUpdates && array_key_exists('stage', $payload)) {
            $updates['stage'] = $payload['stage'];
        }

        if ($allowProgressUpdates && $logMessage !== null) {
            $updates['last_log_message'] = $logMessage;
        }

        if ($shouldUpdateStatus) {
            $updates['status'] = $incomingStatus;
            $updates['error'] = $incomingStatus === ProjectStatus::failed ? ($payload['error'] ?? null) : null;

            if ($incomingStatus === ProjectStatus::completed && !array_key_exists('progress_percent', $payload)) {
                $updates['progress_percent'] = 100;
            }
        }

        $project->forceFill($updates)->save();

        if ($allowProgressUpdates && !empty($logMessage)) {
            PipelineEvent::log(
                type: 'worker.log',
                message: (string) $logMessage,
                payload: [
                    'job_id' => $incomingJobId,
                    'progress_percent' => $payload['progress_percent'] ?? null,
                    'stage' => $payload['stage'] ?? null,
                ],
                project: $project,
            );
        }

        $effectiveStatus = $project->status;

        if ($effectiveStatus === ProjectStatus::failed) {
            Clip::query()
                ->where('project_id', $project->id)
                ->update(['status' => ClipStatus::failed]);
        }

        $clips = data_get($payload, 'artifacts.clips', []);
        if (is_array($clips)) {
            foreach ($clips as $clipPayload) {
                if (!is_array($clipPayload)) {
                    continue;
                }

                $externalId = (string) ($clipPayload['clip_id'] ?? '');
                if ($externalId === '') {
                    continue;
                }

                $clipStatus = match ($effectiveStatus) {
                    ProjectStatus::completed => ClipStatus::ready,
                    ProjectStatus::failed => ClipStatus::failed,
                    default => ClipStatus::pending,
                };

                $clip = Clip::query()->updateOrCreate(
                    [
                        'project_id' => (string) $project->id,
                        'external_id' => $externalId,
                    ],
                    [
                        'status' => $clipStatus,
                        'start_seconds' => $clipPayload['start_seconds'] ?? null,
                        'end_seconds' => $clipPayload['end_seconds'] ?? null,
                        'score' => $clipPayload['score'] ?? null,
                        'reason' => $clipPayload['reason'] ?? null,
                        'title' => $clipPayload['title'] ?? null,
                        'title_candidates' => $clipPayload['title_candidates'] ?? null,
                        'video_path' => $clipPayload['video_path'] ?? null,
                        'subtitles_ass_path' => $clipPayload['subtitles_ass_path'] ?? null,
                        'subtitles_srt_path' => $clipPayload['subtitles_srt_path'] ?? null,
                    ],
                );

                PipelineEvent::log(
                    type: 'worker.clip.upserted',
                    payload: ['external_id' => $externalId],
                    project: $project,
                    clip: $clip,
                );
            }
        }

        if ($incomingStatus === null) {
            PipelineEvent::log(
                type: 'worker.callback.unknown_status',
                message: (string) $payload['status'],
                project: $project,
            );
        }

        return response()->json(['ok' => true]);
    }

    private function mapProjectStatus(string $workerStatus): ?ProjectStatus
    {
        return match ($workerStatus) {
            'queued' => ProjectStatus::queued,
            'processing' => ProjectStatus::processing,
            'completed' => ProjectStatus::completed,
            'failed' => ProjectStatus::failed,
            default => null,
        };
    }

    private function shouldUpdateStatus(ProjectStatus $current, ProjectStatus $incoming): bool
    {
        if (in_array($current, [ProjectStatus::completed, ProjectStatus::failed], true)) {
            return false;
        }

        return $this->statusRank($incoming) >= $this->statusRank($current);
    }

    private function statusRank(ProjectStatus $status): int
    {
        return match ($status) {
            ProjectStatus::queued => 0,
            ProjectStatus::processing => 1,
            ProjectStatus::completed => 2,
            ProjectStatus::failed => 3,
        };
    }
}