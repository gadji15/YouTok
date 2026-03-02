<x-app-layout>
    <x-slot name="header">
        <div class="flex items-center justify-between">
            <h2 class="font-semibold text-xl text-gray-800 leading-tight">TikTok accounts</h2>
            <a href="{{ route('tiktok-accounts.create') }}"
                class="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
                New account
            </a>
        </div>
    </x-slot>

    <div class="py-12">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8">
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    @if (session('status'))
                    <div class="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-800">{{ session('status') }}</div>
                    @endif

                    @if ($accounts->isEmpty())
                    <div class="text-sm text-gray-600">No TikTok accounts yet.</div>
                    @else
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead>
                                <tr>
                                    <th
                                        class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Username</th>
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
                                @foreach ($accounts as $account)
                                <tr>
                                    <td class="px-3 py-2 font-mono text-sm">{{ $account->username }}</td>
                                    <td class="px-3 py-2 text-sm">{{ $account->status->value }}</td>
                                    <td class="px-3 py-2 text-sm text-gray-600">
                                        {{ $account->created_at?->toDateTimeString() }}</td>
                                    <td class="px-3 py-2 text-right space-x-3">
                                        <a class="text-indigo-600 hover:text-indigo-900"
                                            href="{{ route('tiktok-accounts.edit', $account) }}">Edit</a>

                                        <form class="inline" method="POST"
                                            action="{{ route('tiktok-accounts.destroy', $account) }}"
                                            onsubmit="return confirm('Delete this account?');">
                                            @csrf
                                            @method('DELETE')
                                            <button type="submit"
                                                class="text-sm text-red-600 hover:text-red-800">Delete</button>
                                        </form>
                                    </td>
                                </tr>
                                @endforeach
                            </tbody>
                        </table>
                    </div>

                    <div class="mt-4">
                        {{ $accounts->links() }}
                    </div>
                    @endif
                </div>
            </div>
        </div>
    </div>
</x-app-layout>