<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ProjectStatus;
use App\Jobs\SubmitVideoWorkerJob;
use App\Models\Project;
use App\Services\VideoWorkerClient;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SubmitVideoWorkerJobTest extends TestCase
{
    use RefreshDatabase;

    public function test_submit_job_marks_project_failed_when_worker_not_configured(): void
    {
        config()->set('admin.video_worker_base_url', '');

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::queued,
        ]);

        $job = new SubmitVideoWorkerJob((string) $project->id);
        $job->handle(app(VideoWorkerClient::class));

        $project->refresh();
        $this->assertSame(ProjectStatus::failed, $project->status);
        $this->assertNotNull($project->error);
    }
}
