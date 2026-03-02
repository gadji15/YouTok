<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ClipStatus;
use App\Enums\ProjectStatus;
use App\Enums\TikTokAccountStatus;
use App\Models\Clip;
use App\Models\Project;
use App\Models\TikTokAccount;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class ClipPublishTest extends TestCase
{
    use RefreshDatabase;

    public function test_publish_requires_tiktok_bot_base_url_configured(): void
    {
        $email = 'admin@example.com';
        config()->set('admin.emails', [$email]);

        /** @var User $user */
        $user = User::factory()->create([
            'email' => $email,
            'email_verified_at' => now(),
        ]);

        $account = TikTokAccount::query()->create([
            'username' => 'acct1',
            'status' => TikTokAccountStatus::active,
        ]);

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::completed,
        ]);

        $clip = Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c1',
            'status' => ClipStatus::ready,
            'video_path' => '/shared/c1.mp4',
        ]);

        config()->set('admin.tiktok_bot_base_url', '');

        $this->actingAs($user)
            ->post('/clips/'.(string) $clip->id.'/publish', [
                'tiktok_account_id' => (string) $account->id,
                'caption' => 'hello',
            ])
            ->assertRedirect()
            ->assertSessionHas('status');

        $clip->refresh();
        $this->assertNull($clip->tiktok_publish_job_id);
    }

    public function test_publish_queues_job_and_persists_job_id(): void
    {
        $email = 'admin@example.com';
        config()->set('admin.emails', [$email]);

        /** @var User $user */
        $user = User::factory()->create([
            'email' => $email,
            'email_verified_at' => now(),
        ]);

        $account = TikTokAccount::query()->create([
            'username' => 'acct1',
            'status' => TikTokAccountStatus::active,
        ]);

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::completed,
        ]);

        $clip = Clip::query()->create([
            'project_id' => (string) $project->id,
            'external_id' => 'c1',
            'status' => ClipStatus::ready,
            'video_path' => '/shared/c1.mp4',
        ]);

        config()->set('admin.tiktok_bot_base_url', 'http://tiktok-bot.test');
        config()->set('admin.tiktok_bot_internal_secret', 'secret');

        Http::fake([
            'http://tiktok-bot.test/publish' => Http::response([
                'status' => 'accepted',
                'job_id' => 'job_123',
                'mode' => 'stub',
            ], 202),
        ]);

        $this->actingAs($user)
            ->post('/clips/'.(string) $clip->id.'/publish', [
                'tiktok_account_id' => (string) $account->id,
                'caption' => 'hello #test',
            ])
            ->assertRedirect();

        $clip->refresh();

        $this->assertSame('job_123', $clip->tiktok_publish_job_id);
        $this->assertSame('queued', $clip->tiktok_publish_status);
        $this->assertSame('hello #test', $clip->tiktok_caption);
    }
}