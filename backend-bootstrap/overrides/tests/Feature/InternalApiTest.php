<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ClipStatus;
use App\Enums\ProjectStatus;
use App\Models\Clip;
use App\Models\Project;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class InternalApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_project_create_requires_internal_secret(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        $this->postJson('/api/projects', [
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        ])->assertForbidden();

        $this->withHeader('X-Internal-Secret', 'test-secret')
            ->postJson('/api/projects', [
                'name' => 'Test',
                'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            ])
            ->assertCreated()
            ->assertJsonStructure(['id', 'status']);
    }

    public function test_project_index_requires_internal_secret(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::queued,
            'language' => 'fr',
            'subtitles_enabled' => false,
            'clip_min_seconds' => 60,
            'clip_max_seconds' => 180,
            'subtitle_template' => 'modern',
        ]);

        $this->getJson('/api/projects')->assertForbidden();

        $this->withHeader('X-Internal-Secret', 'test-secret')
            ->getJson('/api/projects')
            ->assertOk()
            ->assertJsonStructure([
                'data' => [
                    ['id', 'name', 'youtube_url', 'status', 'stage', 'progress_percent', 'updated_at', 'created_at'],
                ],
            ]);
    }

    public function test_clip_index_requires_internal_secret(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
        ]);

        Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c1',
            'status' => ClipStatus::ready,
            'video_path' => '/shared/c1.mp4',
        ]);

        $this->getJson('/api/clips')->assertForbidden();

        $this->withHeader('X-Internal-Secret', 'test-secret')
            ->getJson('/api/clips')
            ->assertOk()
            ->assertJsonStructure([
                'data' => [
                    ['id', 'project_id', 'project_name', 'status', 'duration_seconds', 'video_path', 'created_at', 'updated_at'],
                ],
            ]);
    }

    public function test_worker_callback_requires_callback_secret(): void
    {
        config()->set('admin.video_worker_callback_secret', 'cb-secret');

        $payload = [
            'job_id' => 'job-1',
            'project_id' => '00000000-0000-0000-0000-000000000000',
            'status' => 'queued',
        ];

        $this->postJson('/api/worker/callback', $payload)->assertForbidden();
    }
}
