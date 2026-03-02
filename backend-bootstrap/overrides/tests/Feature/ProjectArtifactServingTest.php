<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ProjectStatus;
use App\Models\Project;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

class ProjectArtifactServingTest extends TestCase
{
    use RefreshDatabase;

    public function test_admin_can_download_project_transcript_json_from_shared_storage_root(): void
    {
        $email = 'admin@example.com';
        config()->set('admin.emails', [$email]);

        /** @var User $user */
        $user = User::factory()->create([
            'email' => $email,
            'email_verified_at' => now(),
        ]);

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'shared-root-'.Str::random(8);
        @mkdir($root, 0777, true);
        config()->set('admin.shared_storage_root', $root);

        $path = $root.DIRECTORY_SEPARATOR.'transcript.json';
        file_put_contents($path, json_encode(['ok' => true]));

        $srtPath = $root.DIRECTORY_SEPARATOR.'subtitles.srt';
        file_put_contents($srtPath, "1\n00:00:00,000 --> 00:00:01,000\nhello\n");

        $clipsPath = $root.DIRECTORY_SEPARATOR.'clips.json';
        file_put_contents($clipsPath, json_encode(['clips' => []]));

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::completed,
            'transcript_json_path' => $path,
            'subtitles_srt_path' => $srtPath,
            'clips_json_path' => $clipsPath,
        ]);

        $this->actingAs($user)
            ->get('/projects/'.(string) $project->id.'/artifacts/transcript.json')
            ->assertOk();

        $this->actingAs($user)
            ->get('/projects/'.(string) $project->id.'/artifacts/subtitles.srt')
            ->assertOk();

        $this->actingAs($user)
            ->get('/projects/'.(string) $project->id.'/artifacts/clips.json')
            ->assertOk();
    }

    public function test_admin_cannot_download_project_artifacts_outside_shared_storage_root(): void
    {
        $email = 'admin@example.com';
        config()->set('admin.emails', [$email]);

        /** @var User $user */
        $user = User::factory()->create([
            'email' => $email,
            'email_verified_at' => now(),
        ]);

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'shared-root-'.Str::random(8);
        @mkdir($root, 0777, true);
        config()->set('admin.shared_storage_root', $root);

        $outside = sys_get_temp_dir().DIRECTORY_SEPARATOR.'outside-'.Str::random(8).'.json';
        file_put_contents($outside, json_encode(['nope' => true]));

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::completed,
            'transcript_json_path' => $outside,
        ]);

        $this->actingAs($user)
            ->get('/projects/'.(string) $project->id.'/artifacts/transcript.json')
            ->assertForbidden();
    }
}