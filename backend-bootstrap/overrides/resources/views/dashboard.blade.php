<x-app-layout>
    <x-slot name="header">
        <div class="flex items-center justify-between">
            <h2 class="font-semibold text-xl text-gray-800 leading-tight">
                Dashboard
            </h2>
            <div class="space-x-4">
                <a href="{{ route('projects.index') }}"
                    class="text-sm text-indigo-600 hover:text-indigo-900">Projects</a>
                <a href="{{ route('tiktok-accounts.index') }}"
                    class="text-sm text-indigo-600 hover:text-indigo-900">TikTok accounts</a>
            </div>
        </div>
    </x-slot>

    <div class="py-12">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8 space-y-6">
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div class="rounded-lg bg-white p-6 shadow-sm">
                    <div class="text-sm text-gray-600">Queued</div>
                    <div class="mt-1 text-2xl font-semibold">{{ $counts['queued'] }}</div>
                </div>
                <div class="rounded-lg bg-white p-6 shadow-sm">
                    <div class="text-sm text-gray-600">Processing</div>
                    <div class="mt-1 text-2xl font-semibold">{{ $counts['processing'] }}</div>
                </div>
                <div class="rounded-lg bg-white p-6 shadow-sm">
                    <div class="text-sm text-gray-600">Completed</div>
                    <div class="mt-1 text-2xl font-semibold">{{ $counts['completed'] }}</div>
                </div>
                <div class="rounded-lg bg-white p-6 shadow-sm">
                    <div class="text-sm text-gray-600">Failed</div>
                    <div class="mt-1 text-2xl font-semibold">{{ $counts['failed'] }}</div>
                </div>
            </div>

            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    <div class="flex items-center justify-between">
                        <h3 class="text-lg font-semibold">Latest projects</h3>
                        <a href="{{ route('projects.create') }}"
                            class="text-sm text-indigo-600 hover:text-indigo-900">New</a>
                    </div>

                    @if ($projects->isEmpty())
                    <div class="mt-2 text-sm text-gray-600">No projects yet.</div>
                    @else
                    <div class="mt-4 overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead>
                                <tr>
                                    <th
                                        class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Name</th>
                                    <th
                                        class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Status</th>
                                    <th
                                        class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Created</th>
                                    <th class="px-3 py-2"></th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200">
                                @foreach ($projects as $project)
                                <tr>
                                    <td class="px-3 py-2 font-medium">{{ $project->name }}</td>
                                    <td class="px-3 py-2">{{ $project->status->value }}</td>
                                    <td class="px-3 py-2 text-sm text-gray-600">
                                        {{ $project->created_at?->toDateTimeString() }}</td>
                                    <td class="px-3 py-2 text-right">
                                        <a class="text-indigo-600 hover:text-indigo-900"
                                            href="{{ route('projects.show', $project) }}">View</a>
                                    </td>
                                </tr>
                                @endforeach
                            </tbody>
                        </table>
                    </div>
                    @endif
                </div>
            </div>

            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    <h3 class="text-lg font-semibold">Latest pipeline events</h3>

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
                            <div class="mt-1 text-sm text-gray-700">
                                @if ($event->project)
                                <a class="text-indigo-600 hover:text-indigo-900"
                                    href="{{ route('projects.show', $event->project) }}">{{ $event->project->name }}</a>
                                @else
                                <span class="text-gray-500">(no project)</span>
                                @endif
                            </div>
                            @if ($event->message)
                            <div class="mt-1 text-sm text-gray-700">{{ $event->message }}</div>
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