<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ClipStatus;
use App\Enums\ProjectStatus;
use App\Models\Clip;
use App\Models\PipelineEvent;
use App\Models\Project;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class WorkerCallbackTest extends TestCase
{
    use RefreshDatabase;

    public function test_worker_callback_does_not_downgrade_project_status(): void
    {
        config()->set('admin.video_worker_callback_secret', 'cb-secret');

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
            'worker_job_id' => 'job-1',
        ]);

        $this->withHeader('X-Callback-Secret', 'cb-secret')
            ->postJson('/api/worker/callback', [
                'job_id' => 'job-1',
                'project_id' => (string) $project->id,
                'status' => 'queued',
            ])
            ->assertOk();

        $project->refresh();
        $this->assertSame(ProjectStatus::processing, $project->status);
    }

    public function test_worker_callback_updates_progress_stage_and_log_message(): void
    {
        config()->set('admin.video_worker_callback_secret', 'cb-secret');

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
            'worker_job_id' => 'job-1',
        ]);

        $this->withHeader('X-Callback-Secret', 'cb-secret')
            ->postJson('/api/worker/callback', [
                'job_id' => 'job-1',
                'project_id' => (string) $project->id,
                'status' => 'processing',
                'progress_percent' => 42,
                'stage' => 'transcribing',
                'log_message' => 'step started',
            ])
            ->assertOk();

        $project->refresh();
        $this->assertSame(42, $project->progress_percent);
        $this->assertSame('transcribing', $project->stage);
        $this->assertSame('step started', $project->last_log_message);

        $this->assertTrue(PipelineEvent::query()
            ->where('project_id', $project->id)
            ->where('type', 'worker.log')
            ->where('message', 'step started')
            ->exists());
    }

    public function test_worker_callback_accepts_message_alias_for_log_message(): void
    {
        config()->set('admin.video_worker_callback_secret', 'cb-secret');

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
            'worker_job_id' => 'job-1',
        ]);

        $this->withHeader('X-Callback-Secret', 'cb-secret')
            ->postJson('/api/worker/callback', [
                'job_id' => 'job-1',
                'project_id' => (string) $project->id,
                'status' => 'processing',
                'progress_percent' => 10,
                'stage' => 'download',
                'message' => 'Downloading source video',
            ])
            ->assertOk();

        $project->refresh();
        $this->assertSame('Downloading source video', $project->last_log_message);

        $this->assertTrue(PipelineEvent::query()
            ->where('project_id', $project->id)
            ->where('type', 'worker.log')
            ->where('message', 'Downloading source video')
            ->exists());
    }

    public function test_worker_callback_ignores_mismatched_job_id(): void
    {
        config()->set('admin.video_worker_callback_secret', 'cb-secret');

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
            'worker_job_id' => 'job-1',
        ]);

        $this->withHeader('X-Callback-Secret', 'cb-secret')
            ->postJson('/api/worker/callback', [
                'job_id' => 'job-2',
                'project_id' => (string) $project->id,
                'status' => 'completed',
                'artifacts' => [
                    'clips' => [
                        [
                            'clip_id' => 'c1',
                            'video_path' => '/shared/c1.mp4',
                        ],
                    ],
                ],
            ])
            ->assertOk();

        $project->refresh();
        $this->assertSame('job-1', $project->worker_job_id);
        $this->assertSame(ProjectStatus::processing, $project->status);
        $this->assertSame(0, Clip::query()->where('project_id', $project->id)->count());
    }

    public function test_worker_callback_marks_project_complete_and_upserts_clips(): void
    {
        config()->set('admin.video_worker_callback_secret', 'cb-secret');

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
            'worker_job_id' => 'job-1',
            'error' => 'previous error',
        ]);

        $this->withHeader('X-Callback-Secret', 'cb-secret')
            ->postJson('/api/worker/callback', [
                'job_id' => 'job-1',
                'project_id' => (string) $project->id,
                'status' => 'completed',
                'artifacts' => [
                    'source_video_path' => '/shared/source.mp4',
                    'clips' => [
                        [
                            'clip_id' => 'c1',
                            'start_seconds' => 1.25,
                            'end_seconds' => 4.25,
                            'score' => 0.5,
                            'reason' => 'interesting',
                            'title' => 'Un hook viral pour tester',
                            'title_candidates' => [
                                'provider' => 'heuristic',
                                'description' => 'Desc',
                                'hashtags' => ['#pourtoi', '#conseils', '#tiktok'],
                                'candidates' => [
                                    ['title' => 'Un hook viral pour tester', 'score' => 0.9],
                                    ['title' => 'Et si tu faisais ça ?', 'score' => 0.7],
                                ],
                                'top3' => ['Un hook viral pour tester', 'Et si tu faisais ça ?'],
                            ],
                            'quality_summary' => [
                                'template' => 'cinematic_karaoke',
                                'ui_safe_ymin' => 0.78,
                                'final_overlap' => [
                                    'face_overlap_ratio_p95' => 0.03,
                                    'ui_overlap_ratio_p95' => 0.0,
                                ],
                            ],
                            'video_path' => '/shared/c1.mp4',
                            'subtitles_ass_path' => '/shared/c1.ass',
                            'subtitles_srt_path' => '/shared/c1.srt',
                        ],
                    ],
                ],
            ])
            ->assertOk();

        $project->refresh();
        $this->assertSame(ProjectStatus::completed, $project->status);
        $this->assertNull($project->error);
        $this->assertSame('/shared/source.mp4', $project->source_video_path);
        $this->assertSame(100, $project->progress_percent);

        $clip = Clip::query()->where('project_id', $project->id)->where('external_id', 'c1')->first();
        $this->assertNotNull($clip);
        $this->assertSame(ClipStatus::ready, $clip->status);
        $this->assertSame('/shared/c1.mp4', $clip->video_path);
        $this->assertSame('Un hook viral pour tester', $clip->title);
        $this->assertIsArray($clip->title_candidates);
        $this->assertSame('heuristic', $clip->title_candidates['provider']);

        $this->assertIsArray($clip->quality_summary);
        $this->assertSame('cinematic_karaoke', $clip->quality_summary['template']);
    }

    public function test_worker_callback_does_not_overwrite_progress_after_completion(): void
    {
        config()->set('admin.video_worker_callback_secret', 'cb-secret');

        $project = Project::query()->create([
            'name' => 'Test',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::completed,
            'worker_job_id' => 'job-1',
            'stage' => 'completed',
            'progress_percent' => 100,
            'last_log_message' => 'Done',
        ]);

        $this->withHeader('X-Callback-Secret', 'cb-secret')
            ->postJson('/api/worker/callback', [
                'job_id' => 'job-1',
                'project_id' => (string) $project->id,
                'status' => 'processing',
                'stage' => 'render_clips',
                'progress_percent' => 90,
                'message' => 'Rendering clips',
            ])
            ->assertOk();

        $project->refresh();
        $this->assertSame(ProjectStatus::completed, $project->status);
        $this->assertSame('completed', $project->stage);
        $this->assertSame(100, $project->progress_percent);
        $this->assertSame('Done', $project->last_log_message);
    }

    public function test_worker_callback_returns_ok_when_project_was_deleted(): void
    {
        config()->set('admin.video_worker_callback_secret', 'cb-secret');

        $project = Project::query()->create([
            'name' => 'ToDelete',
            'youtube_url' => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'status' => ProjectStatus::processing,
            'worker_job_id' => 'job-1',
        ]);

        $projectId = (string) $project->id;
        $project->delete();

        $this->withHeader('X-Callback-Secret', 'cb-secret')
            ->postJson('/api/worker/callback', [
                'job_id' => 'job-1',
                'project_id' => $projectId,
                'status' => 'processing',
                'stage' => 'transcribe',
                'progress_percent' => 50,
                'message' => 'Transcribing audio',
            ])
            ->assertOk();

        $this->assertSame(0, Project::query()->where('id', $projectId)->count());
    }
}