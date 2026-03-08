<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ProjectStatus;
use App\Jobs\SubmitVideoWorkerJob;
use App\Models\Project;
use Illuminate\Foundation\Testing\DatabaseMigrations;
use Illuminate\Support\Facades\Bus;
use Tests\TestCase;

class ProjectApiRetryTest extends TestCase
{
    use DatabaseMigrations;

    public function test_internal_api_project_retry_resets_project_and_dispatches_worker_job(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        // Prevent real worker submissions during tests.
        Bus::fake();
        config()->set('admin.video_worker_base_url', '');

        $project = Project::query()->create([
            'name' => 'Retry Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
            'worker_job_id' => 'job_old',
            'stage' => 'render_clips',
            'progress_percent' => 99,
            'last_log_message' => 'Rendering clip 8/8...',
        ]);

        $this->withHeader('X-Internal-Secret', 'test-secret')
            ->postJson('/api/projects/'.urlencode((string) $project->id).'/retry')
            ->assertOk();

        $project->refresh();

        $this->assertSame(ProjectStatus::queued, $project->status);
        $this->assertSame('queued', $project->stage);
        $this->assertSame(0, $project->progress_percent);
        $this->assertNotNull($project->worker_job_id);
        $this->assertStringStartsWith('retry-', (string) $project->worker_job_id);
        $this->assertNull($project->error);

        Bus::assertDispatched(SubmitVideoWorkerJob::class, function (SubmitVideoWorkerJob $job) use ($project): bool {
            return $job->projectId === (string) $project->id;
        });
    }
}
