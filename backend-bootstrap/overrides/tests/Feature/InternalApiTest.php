<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ClipStatus;
use App\Enums\ProjectStatus;
use App\Models\Clip;
use App\Models\Project;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
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
            'subtitle_template' => 'modern_karaoke',
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

    public function test_project_delete_requires_internal_secret_and_deletes_artifacts(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'shared-root-'.Str::random(8);
        @mkdir($root, 0777, true);
        config()->set('admin.shared_storage_root', $root);

        $sourceVideoPath = $root.DIRECTORY_SEPARATOR.'source.mp4';
        $audioPath = $root.DIRECTORY_SEPARATOR.'audio.wav';
        $transcriptJsonPath = $root.DIRECTORY_SEPARATOR.'transcript.json';
        file_put_contents($sourceVideoPath, 'video');
        file_put_contents($audioPath, 'audio');
        file_put_contents($transcriptJsonPath, '{"ok":true}');

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
            'source_video_path' => $sourceVideoPath,
            'audio_path' => $audioPath,
            'transcript_json_path' => $transcriptJsonPath,
        ]);

        $clipVideoPath = $root.DIRECTORY_SEPARATOR.'clip.mp4';
        file_put_contents($clipVideoPath, 'clip');
        $clip = Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c1',
            'status' => ClipStatus::ready,
            'video_path' => $clipVideoPath,
        ]);

        $this->deleteJson('/api/projects/'.(string) $project->id)->assertForbidden();

        $this->withHeader('X-Internal-Secret', 'test-secret')
            ->deleteJson('/api/projects/'.(string) $project->id)
            ->assertNoContent();

        $this->assertDatabaseMissing('projects', ['id' => (string) $project->id]);
        $this->assertDatabaseMissing('clips', ['id' => (string) $clip->id]);

        self::assertFileDoesNotExist($sourceVideoPath);
        self::assertFileDoesNotExist($audioPath);
        self::assertFileDoesNotExist($transcriptJsonPath);
        self::assertFileDoesNotExist($clipVideoPath);
    }

    public function test_clip_delete_requires_internal_secret_and_deletes_artifacts(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'shared-root-'.Str::random(8);
        @mkdir($root, 0777, true);
        config()->set('admin.shared_storage_root', $root);

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
        ]);

        $clipVideoPath = $root.DIRECTORY_SEPARATOR.'clip.mp4';
        file_put_contents($clipVideoPath, 'clip');

        $clip = Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c1',
            'status' => ClipStatus::ready,
            'video_path' => $clipVideoPath,
        ]);

        $this->deleteJson('/api/clips/'.(string) $clip->id)->assertForbidden();

        $this->withHeader('X-Internal-Secret', 'test-secret')
            ->deleteJson('/api/clips/'.(string) $clip->id)
            ->assertNoContent();

        $this->assertDatabaseHas('projects', ['id' => (string) $project->id]);
        $this->assertDatabaseMissing('clips', ['id' => (string) $clip->id]);

        self::assertFileDoesNotExist($clipVideoPath);
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
