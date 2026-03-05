# Laravel callback reference implementation

This repo bootstraps a Laravel backend via `backend-bootstrap/`. This document exists as a quick reference for the callback contract expected by `video-worker`.

## Endpoint

- `POST /api/worker/callback`
- Header: `X-Callback-Secret: <shared secret>`

## Payload schema

See `services/video-worker/README.md` for a concrete example.

Top-level fields:

- `job_id` (string)
- `project_id` (string)
- `status` (`queued` | `processing` | `completed` | `failed`)
- `artifacts` (object|null)
  - `source_video_path` (string|null)
  - `audio_path` (string|null)
  - `transcript_json_path` (string|null)
  - `subtitles_srt_path` (string|null)
  - `clips_json_path` (string|null)
  - `words_json_path` (string|null)
  - `segments_json_path` (string|null)
  - `source_metadata_json_path` (string|null)
  - `source_thumbnail_path` (string|null)
  - `clips` (array)
    - `clip_id` (string)
    - `start_seconds` (number)
    - `end_seconds` (number)
    - `score` (number)
    - `reason` (string|null)
    - `title` (string|null)
    - `video_path` (string)
    - `subtitles_srt_path` (string|null)
    - `subtitles_ass_path` (string|null)
- `error` (string|null)

## Laravel implementation sketch

### Config

`config/services.php`

```php
return [
    // ...
    'video_worker' => [
        'callback_secret' => env('VIDEO_WORKER_CALLBACK_SECRET'),
    ],
];
```

`.env`

```env
VIDEO_WORKER_CALLBACK_SECRET=supersecret
```

### Route

`routes/api.php`

```php
use App\Http\Controllers\VideoWorkerCallbackController;

Route::post('/worker/callback', VideoWorkerCallbackController::class);
```

### Controller

`app/Http/Controllers/VideoWorkerCallbackController.php`

```php
<?php

namespace App\Http\Controllers;

use App\Models\Clip;
use App\Models\Project;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class VideoWorkerCallbackController extends Controller
{
    public function __invoke(Request $request)
    {
        $expected = (string) config('services.video_worker.callback_secret');
        $provided = (string) $request->header('X-Callback-Secret', '');

        if ($expected === '' || !hash_equals($expected, $provided)) {
            abort(403);
        }

        $data = $request->validate([
            'job_id' => ['required', 'string'],
            'project_id' => ['required', 'string'],
            'status' => ['required', 'in:queued,processing,completed,failed'],
            'error' => ['nullable', 'string'],
            'artifacts' => ['nullable', 'array'],
            'artifacts.source_video_path' => ['nullable', 'string'],
            'artifacts.audio_path' => ['nullable', 'string'],
            'artifacts.transcript_json_path' => ['nullable', 'string'],
            'artifacts.subtitles_srt_path' => ['nullable', 'string'],
            'artifacts.clips_json_path' => ['nullable', 'string'],
            'artifacts.words_json_path' => ['nullable', 'string'],
            'artifacts.segments_json_path' => ['nullable', 'string'],
            'artifacts.source_metadata_json_path' => ['nullable', 'string'],
            'artifacts.source_thumbnail_path' => ['nullable', 'string'],
            'artifacts.clips' => ['nullable', 'array'],
            'artifacts.clips.*.clip_id' => ['required_with:artifacts.clips', 'string'],
            'artifacts.clips.*.start_seconds' => ['required_with:artifacts.clips', 'numeric'],
            'artifacts.clips.*.end_seconds' => ['required_with:artifacts.clips', 'numeric'],
            'artifacts.clips.*.score' => ['required_with:artifacts.clips', 'numeric'],
            'artifacts.clips.*.reason' => ['nullable', 'string'],
            'artifacts.clips.*.title' => ['nullable', 'string'],
            'artifacts.clips.*.video_path' => ['required_with:artifacts.clips', 'string'],
            'artifacts.clips.*.subtitles_srt_path' => ['nullable', 'string'],
            'artifacts.clips.*.subtitles_ass_path' => ['nullable', 'string'],
        ]);

        DB::transaction(function () use ($data) {
            $project = Project::where('id', $data['project_id'])->lockForUpdate()->firstOrFail();

            // Map status => whatever your Project model uses.
            // Example columns shown here; rename to match your schema.
            $project->video_worker_job_id = $data['job_id'];
            $project->video_worker_status = $data['status'];
            $project->video_worker_error = $data['error'] ?? null;

            $artifacts = $data['artifacts'] ?? null;
            if ($artifacts) {
                $project->source_video_path = $artifacts['source_video_path'] ?? null;
                $project->audio_path = $artifacts['audio_path'] ?? null;
                $project->transcript_json_path = $artifacts['transcript_json_path'] ?? null;
                $project->subtitles_srt_path = $artifacts['subtitles_srt_path'] ?? null;
                $project->clips_json_path = $artifacts['clips_json_path'] ?? null;
                $project->words_json_path = $artifacts['words_json_path'] ?? null;
                $project->segments_json_path = $artifacts['segments_json_path'] ?? null;
                $project->source_metadata_json_path = $artifacts['source_metadata_json_path'] ?? null;
                $project->source_thumbnail_path = $artifacts['source_thumbnail_path'] ?? null;
            }

            $project->save();

            if (($data['status'] ?? null) === 'completed') {
                $clips = $artifacts['clips'] ?? [];

                // Idempotency: clear/recreate, or upsert by (project_id, clip_id).
                Clip::where('project_id', $project->id)->delete();

                foreach ($clips as $clip) {
                    Clip::create([
                        'project_id' => $project->id,
                        'external_id' => $clip['clip_id'],
                        'start_seconds' => $clip['start_seconds'],
                        'end_seconds' => $clip['end_seconds'],
                        'score' => $clip['score'],
                        'reason' => $clip['reason'] ?? null,
                        'title' => $clip['title'] ?? null,
                        'video_path' => $clip['video_path'],
                        'subtitles_srt_path' => $clip['subtitles_srt_path'] ?? null,
                        'subtitles_ass_path' => $clip['subtitles_ass_path'] ?? null,
                    ]);
                }
            }
        });

        return response()->json(['ok' => true]);
    }
}
```

Notes:

- The snippet uses `403` for bad secret.
- For idempotency, consider upserting clips instead of delete/recreate.
- Update the column names to match your real `projects` / `clips` schema.
