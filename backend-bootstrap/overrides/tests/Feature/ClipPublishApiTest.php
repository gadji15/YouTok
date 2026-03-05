<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ClipStatus;
use App\Enums\ProjectStatus;
use App\Enums\TikTokAccountStatus;
use App\Models\Clip;
use App\Models\Project;
use App\Models\TikTokAccount;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class ClipPublishApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_publish_requires_internal_secret(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

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

        $this->postJson('/api/clips/'.(string) $clip->id.'/publish', [
            'tiktok_account_id' => '00000000-0000-0000-0000-000000000000',
            'caption' => 'hello',
        ])->assertForbidden();
    }

    public function test_publish_queues_job_and_persists_job_id(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

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

        $this->withHeader('X-Internal-Secret', 'test-secret')
            ->postJson('/api/clips/'.(string) $clip->id.'/publish', [
                'tiktok_account_id' => (string) $account->id,
                'caption' => 'hello #test',
            ])
            ->assertStatus(202)
            ->assertJson([
                'status' => 'queued',
                'job_id' => 'job_123',
            ]);

        $clip->refresh();

        $this->assertSame('job_123', $clip->tiktok_publish_job_id);
        $this->assertSame('queued', $clip->tiktok_publish_status);
        $this->assertSame('hello #test', $clip->tiktok_caption);
        $this->assertSame((string) $account->id, (string) $clip->tiktok_account_id);
    }
}