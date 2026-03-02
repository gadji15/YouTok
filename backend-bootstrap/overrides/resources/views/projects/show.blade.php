<x-app-layout>
    <x-slot name="header">
        <div class="flex items-center justify-between">
            <div>
                <h2 class="font-semibold text-xl text-gray-800 leading-tight">
                    {{ $project->name }}
                </h2>
                <div class="mt-1 text-sm text-gray-600">
                    Status: <span id="project-status">{{ $project->status->value }}</span>
                    <span class="ml-2">Stage: <span id="project-stage">{{ $project->stage ?? '—' }}</span></span>
                </div>
                <div class="mt-2">
                    <div class="flex items-center justify-between text-xs text-gray-600">
                        <div>Progress: <span id="project-progress-text">{{ $project->progress_percent ?? 0 }}%</span></div>
                        <div>Updated: <span id="project-updated-at">{{ $project->updated_at?->toDateTimeString() }}</span></div>
                    </div>
                    <div class="mt-1 h-2 w-full rounded bg-gray-200">
                        <div id="project-progress-bar" class="h-2 rounded bg-indigo-600" style="width: {{ (int) ($project->progress_percent ?? 0) }}%"></div>
                    </div>
                    <div class="mt-2 text-xs text-gray-600">Latest: <span id="project-last-log" class="font-mono">{{ $project->last_log_message ?? '—' }}</span></div>
                    <div id="project-processing-complete" class="mt-2 hidden text-sm text-green-700">Processing complete.</div>
                </div>
            </div>
            <a href="{{ route('projects.index') }}" class="text-sm text-gray-600 hover:text-gray-900">Back</a>
        </div>
    </x-slot>

    <div class="py-12">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8 space-y-6">
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    <div class="flex items-start justify-between gap-4">
                        <div class="space-y-2">
                            <div>
                                <div class="text-sm text-gray-600">YouTube URL</div>
                                <a class="text-indigo-600 hover:text-indigo-900" href="{{ $project->youtube_url }}" target="_blank" rel="noreferrer">{{ $project->youtube_url }}</a>
                            </div>
                            <div>
                                <div class="text-sm text-gray-600">Worker job id</div>
                                <div class="font-mono text-sm">{{ $project->worker_job_id ?? '—' }}</div>
                            </div>

                            <div>
                                <div class="text-sm text-gray-600">Project artifacts</div>
                                <div class="mt-1 text-sm space-x-3">
                                    @if ($project->transcript_json_path)
                                        <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('projects.artifacts.transcript', $project) }}">transcript.json</a>
                                    @else
                                        <span class="text-gray-400">transcript.json —</span>
                                    @endif

                                    @if ($project->subtitles_srt_path)
                                        <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('projects.artifacts.subtitles', $project) }}">subtitles.srt</a>
                                    @else
                                        <span class="text-gray-400">subtitles.srt —</span>
                                    @endif

                                    @if ($project->clips_json_path)
                                        <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('projects.artifacts.clips', $project) }}">clips.json</a>
                                    @else
                                        <span class="text-gray-400">clips.json —</span>
                                    @endif
                                </div>
                            </div>

                            @if ($project->error)
                                <div>
                                    <div class="text-sm text-gray-600">Error</div>
                                    <div class="mt-1 rounded bg-red-50 p-2 text-sm text-red-800 whitespace-pre-wrap">{{ $project->error }}</div>
                                </div>
                            @endif
                        </div>

                        <form method="POST" action="{{ route('projects.destroy', $project) }}" onsubmit="return confirm('Delete this project? This will remove its clips and events.');">
                            @csrf
                            @method('DELETE')
                            <button type="submit" class="inline-flex items-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-500">Delete</button>
                        </form>
                    </div>
                </div>
            </div>

            @php($clipsDisabled = $project->status->value !== 'completed')
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    <h3 class="text-lg font-semibold">Clips</h3>

                    <div id="clips-help" class="mt-2 text-sm text-gray-600 {{ $clipsDisabled ? '' : 'hidden' }}">
                        Clips will appear when processing completes.
                    </div>

                    <div id="clips-section" class="{{ $clipsDisabled ? 'opacity-50 pointer-events-none select-none' : '' }}">
                        @if ($clips->isEmpty())
                            <div class="mt-2 text-sm text-gray-600">No clips yet.</div>
                        @else
                            <div class="mt-4 overflow-x-auto">
                                <table class="min-w-full divide-y divide-gray-200">
                                    <thead>
                                        <tr>
                                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">External id</th>
                                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Range</th>
                                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
                                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Reason</th>
                                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Video</th>
                                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subtitles</th>
                                            <th class="px-3 py-2"></th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-gray-200">
                                        @foreach ($clips as $clip)
                                            <tr>
                                                <td class="px-3 py-2 font-mono text-sm">{{ $clip->external_id ?? $clip->id }}</td>
                                                <td class="px-3 py-2 text-sm text-gray-700">
                                                    {{ $clip->start_seconds ?? '—' }}s → {{ $clip->end_seconds ?? '—' }}s
                                                </td>
                                                <td class="px-3 py-2 text-sm text-gray-700">{{ $clip->score ?? '—' }}</td>
                                                <td class="px-3 py-2 text-sm text-gray-700">{{ $clip->reason ?? '—' }}</td>
                                                <td class="px-3 py-2 text-sm">{{ $clip->status->value }}</td>
                                                <td class="px-3 py-2 text-sm">
                                                    @if ($clip->video_path)
                                                        <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('clips.video', $clip) }}" target="_blank" rel="noreferrer">Open</a>
                                                    @else
                                                        <span class="text-gray-400">—</span>
                                                    @endif
                                                </td>
                                                <td class="px-3 py-2 text-sm">
                                                    <div class="space-x-3">
                                                        @if ($clip->subtitles_ass_path)
                                                            <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('clips.subtitles.ass', $clip) }}">.ass</a>
                                                        @else
                                                            <span class="text-gray-400">.ass —</span>
                                                        @endif

                                                        @if ($clip->subtitles_srt_path)
                                                            <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('clips.subtitles.srt', $clip) }}">.srt</a>
                                                        @else
                                                            <span class="text-gray-400">.srt —</span>
                                                        @endif
                                                    </div>
                                                </td>
                                                <td class="px-3 py-2 text-right">
                                                    <a class="text-indigo-600 hover:text-indigo-900" href="{{ route('clips.show', $clip) }}">Details</a>
                                                </td>
                                            </tr>
                                        @endforeach
                                    </tbody>
                                </table>
                            </div>
                        @endif
                    </div>
                </div>
            </div>

            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    <h3 class="text-lg font-semibold">Pipeline events</h3>

                    <div id="pipeline-events-empty" class="mt-2 text-sm text-gray-600 {{ $events->isEmpty() ? '' : 'hidden' }}">No events yet.</div>

                    <div id="pipeline-events-list" class="mt-4 space-y-3">
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
                </div>
            </div>
        </div>
    </div>

    <script>
        (function () {
            const statusUrl = @json(route('projects.status', $project));
            let lastStatus = @json($project->status?->value ?? $project->status);

            const els = {
                status: document.getElementById('project-status'),
                stage: document.getElementById('project-stage'),
                progressText: document.getElementById('project-progress-text'),
                progressBar: document.getElementById('project-progress-bar'),
                updatedAt: document.getElementById('project-updated-at'),
                lastLog: document.getElementById('project-last-log'),
                processingComplete: document.getElementById('project-processing-complete'),
                clipsHelp: document.getElementById('clips-help'),
                clipsSection: document.getElementById('clips-section'),
                eventsEmpty: document.getElementById('pipeline-events-empty'),
                eventsList: document.getElementById('pipeline-events-list'),
            };

            function setProcessingComplete(isComplete) {
                if (!els.processingComplete) return;
                els.processingComplete.classList.toggle('hidden', !isComplete);
            }

            function setClipsEnabled(enabled) {
                if (!els.clipsSection || !els.clipsHelp) return;

                els.clipsHelp.classList.toggle('hidden', enabled);
                els.clipsSection.classList.toggle('opacity-50', !enabled);
                els.clipsSection.classList.toggle('pointer-events-none', !enabled);
                els.clipsSection.classList.toggle('select-none', !enabled);
            }

            function renderEvents(events) {
                if (!els.eventsList || !els.eventsEmpty) return;

                els.eventsList.replaceChildren();

                if (!Array.isArray(events) || events.length === 0) {
                    els.eventsEmpty.classList.remove('hidden');
                    return;
                }

                els.eventsEmpty.classList.add('hidden');

                for (const event of events) {
                    const card = document.createElement('div');
                    card.className = 'rounded-md border border-gray-200 p-3';

                    const top = document.createElement('div');
                    top.className = 'flex items-center justify-between';

                    const type = document.createElement('div');
                    type.className = 'font-mono text-sm';
                    type.textContent = event.type || '';

                    const createdAt = document.createElement('div');
                    createdAt.className = 'text-xs text-gray-500';
                    createdAt.textContent = event.created_at ? new Date(event.created_at).toLocaleString() : '';

                    top.appendChild(type);
                    top.appendChild(createdAt);
                    card.appendChild(top);

                    if (event.message) {
                        const msg = document.createElement('div');
                        msg.className = 'mt-1 text-sm text-gray-700 whitespace-pre-wrap';
                        msg.textContent = event.message;
                        card.appendChild(msg);
                    }

                    if (event.payload) {
                        const pre = document.createElement('pre');
                        pre.className = 'mt-2 overflow-x-auto rounded bg-gray-50 p-2 text-xs';
                        pre.textContent = JSON.stringify(event.payload, null, 2);
                        card.appendChild(pre);
                    }

                    els.eventsList.appendChild(card);
                }
            }

            async function refresh() {
                const response = await fetch(statusUrl, {
                    method: 'GET',
                    headers: { 'Accept': 'application/json' },
                    cache: 'no-store',
                });

                if (!response.ok) {
                    return;
                }

                const data = await response.json();

                if (data.status && els.status) {
                    els.status.textContent = data.status;
                }

                if (els.stage) {
                    els.stage.textContent = data.stage || '—';
                }

                const progress = typeof data.progress_percent === 'number' ? data.progress_percent : (parseInt(data.progress_percent, 10) || 0);
                if (els.progressText) {
                    els.progressText.textContent = progress + '%';
                }
                if (els.progressBar) {
                    els.progressBar.style.width = Math.max(0, Math.min(100, progress)) + '%';
                }

                if (els.updatedAt && data.updated_at) {
                    els.updatedAt.textContent = new Date(data.updated_at).toLocaleString();
                }

                if (els.lastLog) {
                    els.lastLog.textContent = data.last_log_message || '—';
                }

                setProcessingComplete(data.status === 'completed');
                setClipsEnabled(data.status === 'completed');

                renderEvents(data.events);

                if (lastStatus !== data.status && (data.status === 'completed' || data.status === 'failed')) {
                    window.location.reload();
                    return;
                }

                lastStatus = data.status;
            }

            if (lastStatus === 'completed') {
                setProcessingComplete(true);
                setClipsEnabled(true);
            }

            refresh();
            window.setInterval(refresh, 2500);
        })();
    </script>
</x-app-layout>
