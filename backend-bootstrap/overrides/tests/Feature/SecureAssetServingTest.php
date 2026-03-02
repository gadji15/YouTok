<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ClipStatus;
use App\Enums\ProjectStatus;
use App\Models\Clip;
use App\Models\Project;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

class SecureAssetServingTest extends TestCase
{
    use RefreshDatabase;

    public function test_admin_can_stream_clip_video_from_shared_storage_root(): void
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
            'status' => ProjectStatus::completed,
        ]);

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'shared-root-'.Str::random(8);
        @mkdir($root, 0777, true);
        config()->set('admin.shared_storage_root', $root);

        $videoPath = $root.DIRECTORY_SEPARATOR.'clip.mp4';
        file_put_contents($videoPath, 'test');

        $clip = Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c1',
            'status' => ClipStatus::ready,
            'video_path' => $videoPath,
        ]);

        $this->actingAs($user)
            ->get('/clips/'.(string) $clip->id.'/video')
            ->assertOk();
    }

    public function test_admin_can_download_clip_srt_from_shared_storage_root(): void
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
            'status' => ProjectStatus::completed,
        ]);

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'shared-root-'.Str::random(8);
        @mkdir($root, 0777, true);
        config()->set('admin.shared_storage_root', $root);

        $srtPath = $root.DIRECTORY_SEPARATOR.'clip.srt';
        file_put_contents($srtPath, "1\n00:00:00,000 --> 00:00:01,000\nhello\n");

        $clip = Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c1',
            'status' => ClipStatus::ready,
            'subtitles_srt_path' => $srtPath,
        ]);

        $this->actingAs($user)
            ->get('/clips/'.(string) $clip->id.'/subtitles.srt')
            ->assertOk();
    }

    public function test_admin_cannot_stream_files_outside_shared_storage_root(): void
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
            'status' => ProjectStatus::completed,
        ]);

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'shared-root-'.Str::random(8);
        @mkdir($root, 0777, true);
        config()->set('admin.shared_storage_root', $root);

        $outside = sys_get_temp_dir().DIRECTORY_SEPARATOR.'outside-'.Str::random(8).'.mp4';
        file_put_contents($outside, 'nope');

        $clip = Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c1',
            'status' => ClipStatus::ready,
            'video_path' => $outside,
        ]);

        $this->actingAs($user)
            ->get('/clips/'.(string) $clip->id.'/video')
            ->assertForbidden();
    }
}