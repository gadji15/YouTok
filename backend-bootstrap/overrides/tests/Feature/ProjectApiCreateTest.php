<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ProjectStatus;
use App\Jobs\SubmitVideoWorkerJob;
use App\Models\PipelineEvent;
use App\Models\Project;
use Illuminate\Foundation\Testing\DatabaseMigrations;
use Illuminate\Support\Facades\Bus;
use Tests\TestCase;

class ProjectApiCreateTest extends TestCase
{
    use DatabaseMigrations;

    public function test_internal_api_project_create_dispatches_worker_job(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        Bus::fake();

        $response = $this->withHeader('X-Internal-Secret', 'test-secret')
            ->postJson('/api/projects', [
                'name' => 'Test',
                'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'language' => 'fr',
                'subtitles_enabled' => false,
                'clip_min_seconds' => 60,
                'clip_max_seconds' => 180,
                'subtitle_template' => 'modern',
                'segmentation_mode' => 'chapters',
            ])
            ->assertCreated();

        $projectId = (string) $response->json('id');

        $project = Project::query()->findOrFail($projectId);
        $this->assertSame(ProjectStatus::queued, $project->status);
        $this->assertSame('fr', $project->language);
        $this->assertFalse($project->subtitles_enabled);
        $this->assertSame(60, $project->clip_min_seconds);
        $this->assertSame(180, $project->clip_max_seconds);
        $this->assertSame('modern', $project->subtitle_template);
        $this->assertSame('chapters', $project->segmentation_mode);

        $this->assertTrue(PipelineEvent::query()
            ->where('project_id', $projectId)
            ->where('type', 'project.created')
            ->exists());

        Bus::assertDispatched(SubmitVideoWorkerJob::class, function (SubmitVideoWorkerJob $job) use ($projectId): bool {
            return $job->projectId === $projectId;
        });
    }

    public function test_internal_api_project_create_rejects_non_youtube_urls(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        $this->withHeader('X-Internal-Secret', 'test-secret')
            ->postJson('/api/projects', [
                'name' => 'Test',
                'youtube_url' => 'https://example.com/watch?v=dQw4w9WgXcQ',
            ])
            ->assertUnprocessable();
    }
}
