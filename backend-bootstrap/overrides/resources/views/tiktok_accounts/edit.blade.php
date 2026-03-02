<x-app-layout>
    <x-slot name="header">
        <div class="flex items-center justify-between">
            <h2 class="font-semibold text-xl text-gray-800 leading-tight">Edit TikTok account</h2>
            <a href="{{ route('tiktok-accounts.index') }}" class="text-sm text-gray-600 hover:text-gray-900">Back</a>
        </div>
    </x-slot>

    <div class="py-12">
        <div class="max-w-3xl mx-auto sm:px-6 lg:px-8">
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    <form method="POST" action="{{ route('tiktok-accounts.update', $account) }}" class="space-y-4">
                        @csrf
                        @method('PUT')

                        <div>
                            <label class="block text-sm font-medium text-gray-700">Username</label>
                            <input name="username" value="{{ old('username', $account->username) }}"
                                class="mt-1 block w-full rounded-md border-gray-300" required />
                            @error('username')<div class="mt-1 text-sm text-red-600">{{ $message }}</div>@enderror
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700">Status</label>
                            <select name="status" class="mt-1 block w-full rounded-md border-gray-300" required>
                                @foreach ($statuses as $s)
                                <option value="{{ $s->value }}" @selected(old('status', $account->status->value) ===
                                    $s->value)>{{ $s->value }}</option>
                                @endforeach
                            </select>
                            @error('status')<div class="mt-1 text-sm text-red-600">{{ $message }}</div>@enderror
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700">Notes (optional)</label>
                            <textarea name="notes" class="mt-1 block w-full rounded-md border-gray-300"
                                rows="3">{{ old('notes', $account->notes) }}</textarea>
                            @error('notes')<div class="mt-1 text-sm text-red-600">{{ $message }}</div>@enderror
                        </div>

                        <div class="flex items-center justify-end gap-3">
                            <a href="{{ route('tiktok-accounts.index') }}"
                                class="text-sm text-gray-600 hover:text-gray-900">Cancel</a>
                            <button type="submit"
                                class="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500">Save</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>