<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Enums\ClipStatus;
use App\Enums\ProjectStatus;
use App\Jobs\SubmitVideoWorkerJob;
use App\Models\Clip;
use App\Models\PipelineEvent;
use App\Models\Project;
use App\Support\SharedStorage;
use App\Support\Youtube;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

class ProjectController extends Controller
{
    public function index(): View
    {
        $this->authorize('viewAny', Project::class);

        $projects = Project::query()->orderByDesc('created_at')->paginate(20);

        return view('projects.index', [
            'projects' => $projects,
        ]);
    }

    public function create(): View
    {
        $this->authorize('create', Project::class);

        return view('projects.create');
    }

    public function store(Request $request): RedirectResponse
    {
        $this->authorize('create', Project::class);

        $data = $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'youtube_url' => [
                'required',
                'url',
                'max:2048',
                static function (string $attribute, mixed $value, \Closure $fail): void {
                    if (!is_string($value) || !Youtube::isValidUrl($value)) {
                        $fail('The YouTube URL must be a youtube.com or youtu.be link.');
                    }
                },
            ],
            'originality_enabled' => ['sometimes', 'boolean'],
        ]);

        $project = Project::query()->create([
            'name' => $data['name'],
            'youtube_url' => $data['youtube_url'],
            'originality_mode' => $request->boolean('originality_enabled') ? 'voiceover' : 'none',
            'status' => ProjectStatus::queued,
        ]);

        PipelineEvent::log('project.created', payload: ['youtube_url' => $project->youtube_url], project: $project);

        SubmitVideoWorkerJob::dispatch((string) $project->id)->afterCommit();

        return redirect()->route('projects.show', $project)->with('status', 'Project created.');
    }

    public function show(Project $project): View
    {
        $this->authorize('view', $project);

        $project->load([
            'clips' => $project->segmentation_mode === 'chapters'
                ? fn ($q) => $q->orderBy('start_seconds')->orderBy('created_at')
                : fn ($q) => $q->orderBy('external_id'),
            'pipelineEvents' => fn ($q) => $q->orderByDesc('created_at')->limit(50),
        ]);

        return view('projects.show', [
            'project' => $project,
            'clips' => $project->clips,
            'events' => $project->pipelineEvents,
        ]);
    }

    public function status(Project $project): JsonResponse
    {
        $this->authorize('view', $project);

        $events = PipelineEvent::query()
            ->where('project_id', $project->id)
            ->orderByDesc('created_at')
            ->limit(50)
            ->get()
            ->map(static fn (PipelineEvent $event): array => [
                'id' => $event->id,
                'type' => $event->type,
                'message' => $event->message,
                'payload' => $event->payload,
                'created_at' => $event->created_at?->toISOString(),
            ]);

        $clipsCount = Clip::query()->where('project_id', $project->id)->count();
        $readyClipsCount = Clip::query()
            ->where('project_id', $project->id)
            ->where('status', ClipStatus::ready->value)
            ->count();

        return response()->json([
            'status' => $project->status->value,
            'stage' => $project->stage,
            'progress_percent' => $project->progress_percent,
            'last_log_message' => $project->last_log_message,
            'updated_at' => $project->updated_at?->toISOString(),
            'events' => $events,
            'clips_count' => $clipsCount,
            'ready_clips_count' => $readyClipsCount,
        ]);
    }

    public function destroy(Project $project): RedirectResponse
    {
        $this->authorize('delete', $project);

        $project->load(['clips']);

        SharedStorage::deleteFile($project->source_video_path);
        SharedStorage::deleteFile($project->audio_path);
        SharedStorage::deleteFile($project->transcript_json_path);
        SharedStorage::deleteFile($project->subtitles_srt_path);
        SharedStorage::deleteFile($project->clips_json_path);

        foreach ($project->clips as $clip) {
            SharedStorage::deleteFile($clip->video_path);
            SharedStorage::deleteFile($clip->subtitles_ass_path);
            SharedStorage::deleteFile($clip->subtitles_srt_path);
        }

        // Clean up related records (clips cascade, but pipeline events are nullOnDelete).
        PipelineEvent::query()->where('project_id', $project->id)->delete();
        Clip::query()->where('project_id', $project->id)->delete();

        $project->delete();

        return redirect()->route('projects.index')->with('status', 'Project deleted.');
    }
}