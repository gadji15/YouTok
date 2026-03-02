<x-app-layout>
    <x-slot name="header">
        <div class="flex items-center justify-between">
            <div>
                <h2 class="font-semibold text-xl text-gray-800 leading-tight">
                    Clip {{ $clip->external_id ?? $clip->id }}
                </h2>
                <div class="mt-1 text-sm text-gray-600">Project: <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('projects.show', $clip->project) }}">{{ $clip->project->name }}</a></div>
            </div>
            <a href="{{ route('projects.show', $clip->project) }}" class="text-sm text-gray-600 hover:text-gray-900">Back</a>
        </div>
    </x-slot>

    <div class="py-12">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8 space-y-6">
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900 space-y-6">
                    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                            <div class="text-sm text-gray-600">Status</div>
                            <div class="font-medium">{{ $clip->status->value }}</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-600">Range</div>
                            <div class="font-medium">{{ $clip->start_seconds ?? '—' }}s → {{ $clip->end_seconds ?? '—' }}s</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-600">Score</div>
                            <div class="font-medium">{{ $clip->score ?? '—' }}</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-600">Video</div>
                            @if ($clip->video_path)
                                <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('clips.video', $clip) }}" target="_blank" rel="noreferrer">Open video</a>
                            @else
                                <div class="text-sm text-gray-600">—</div>
                            @endif
                        </div>
                        <div>
                            <div class="text-sm text-gray-600">Subtitles</div>
                            @if ($clip->subtitles_ass_path)
                                <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('clips.subtitles.ass', $clip) }}">Download .ass</a>
                            @else
                                <div class="text-sm text-gray-600">—</div>
                            @endif
                        </div>
                    </div>

                    @if ($clip->video_path)
                        <div>
                            <div class="text-sm text-gray-600">Preview</div>
                            <div class="mt-2">
                                <video class="w-full max-w-sm rounded border border-gray-200" controls preload="metadata" src="{{ route('clips.video', $clip) }}"></video>
                            </div>
                            <div class="mt-2 text-xs text-gray-500">Note: playback works only if the backend container can read the shared volume path.</div>
                        </div>
                    @endif
                </div>
            </div>

            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    <h3 class="text-lg font-semibold">Pipeline events</h3>

                    @if ($events->isEmpty())
                        <div class="mt-2 text-sm text-gray-600">No events yet.</div>
                    @else
                        <div class="mt-4 space-y-3">
                            @foreach ($events as $event)
                                <div class="rounded-md border border-gray-200 p-3">
                                    <div class="flex items-center justify-between">
                                        <div class="font-mono text-sm">{{ $event->type }}</div>
                                        <div class="text-xs text-gray-500">{{ $event->created_at?->toDateTimeString() }}</div>
                                    </div>
                                    @if ($event->message)
                                        <div class="mt-1 text-sm text-gray-700">{{ $event->message }}</div>
                                    @endif
                                    @if ($event->payload)
                                        <pre class="mt-2 overflow-x-auto rounded bg-gray-50 p-2 text-xs">{{ json_encode($event->payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) }}</pre>
                                    @endif
                                </div>
                            @endforeach
                        </div>
                    @endif
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
