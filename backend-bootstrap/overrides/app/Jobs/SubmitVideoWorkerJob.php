<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Enums\ProjectStatus;
use App\Models\PipelineEvent;
use App\Models\Project;
use App\Services\VideoWorkerClient;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;

class SubmitVideoWorkerJob implements ShouldQueue
{
    use Dispatchable;
    use InteractsWithQueue;
    use Queueable;
    use SerializesModels;

    public function __construct(public string $projectId)
    {
    }

    public function handle(VideoWorkerClient $client): void
    {
        $project = Project::query()->findOrFail($this->projectId);

        PipelineEvent::log('worker.submit.started', project: $project);
        Log::info('worker.submit.started', ['project_id' => $project->id]);

        try {
            $jobId = $client->createJob($project);

            if ($jobId === null) {
                $message = 'VIDEO_WORKER_BASE_URL is not set; skipping submit';

                $project->forceFill([
                    'status' => ProjectStatus::failed,
                    'error' => $message,
                ])->save();

                PipelineEvent::log(
                    type: 'worker.disabled',
                    message: $message,
                    project: $project,
                );

                Log::warning('worker.disabled', ['project_id' => $project->id]);

                return;
            }

            // The worker job may not start immediately (single worker / backlog).
            // Mark the project as queued until we receive the first worker callback.
            $project->forceFill([
                'worker_job_id' => $jobId,
                'status' => ProjectStatus::queued,
                'stage' => 'queued',
                'progress_percent' => 0,
                'last_log_message' => 'Queued for processing',
                'error' => null,
            ])->save();

            PipelineEvent::log('worker.submit.completed', payload: ['job_id' => $jobId], project: $project);
            Log::info('worker.submit.completed', ['project_id' => $project->id, 'job_id' => $jobId]);
        } catch (\Throwable $e) {
            $project->forceFill([
                'status' => ProjectStatus::failed,
                'error' => $e->getMessage(),
            ])->save();

            PipelineEvent::log(
                type: 'worker.submit.failed',
                message: $e->getMessage(),
                payload: ['exception' => $e::class],
                project: $project,
            );

            Log::error('worker.submit.failed', [
                'project_id' => $project->id,
                'exception' => $e::class,
                'message' => $e->getMessage(),
            ]);

            throw $e;
        }
    }
}