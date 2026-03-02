<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ClipStatus;
use App\Enums\ProjectStatus;
use App\Models\Clip;
use App\Models\PipelineEvent;
use App\Models\Project;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ProjectStatusEndpointTest extends TestCase
{
    use RefreshDatabase;

    public function test_admin_can_fetch_project_status_json(): void
    {
        $email = 'admin@example.com';
        config()->set('admin.emails', [$email]);

        /** @var User $user */
        $user = User::factory()->create([
            'email' => $email,
            'email_verified_at' => now(),
        ]);

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
            'stage' => 'transcribe',
            'progress_percent' => 50,
            'last_log_message' => 'Transcribing audio',
        ]);

        PipelineEvent::log(type: 'worker.log', message: 'hello', project: $project);

        Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c1',
            'status' => ClipStatus::ready,
            'video_path' => '/shared/c1.mp4',
        ]);

        Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c2',
            'status' => ClipStatus::pending,
        ]);

        $this->actingAs($user)
            ->getJson('/projects/'.(string) $project->id.'/status')
            ->assertOk()
            ->assertJson([
                'status' => 'processing',
                'stage' => 'transcribe',
                'progress_percent' => 50,
                'last_log_message' => 'Transcribing audio',
                'clips_count' => 2,
                'ready_clips_count' => 1,
            ])
            ->assertJsonStructure([
                'updated_at',
                'events' => [
                    ['id', 'type', 'message', 'payload', 'created_at'],
                ],
            ]);
    }
}
