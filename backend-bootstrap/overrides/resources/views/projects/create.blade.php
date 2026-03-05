<x-app-layout>
    <x-slot name="header">
        <h2 class="font-semibold text-xl text-gray-800 leading-tight">
            New project
        </h2>
    </x-slot>

    <div class="py-12">
        <div class="max-w-3xl mx-auto sm:px-6 lg:px-8">
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900">
                    <form method="POST" action="{{ route('projects.store') }}" class="space-y-6" enctype="multipart/form-data">
                        @csrf

                        <div>
                            <x-input-label for="name" value="Project name" />
                            <x-text-input id="name" name="name" type="text" class="mt-1 block w-full"
                                value="{{ old('name') }}" required />
                            <x-input-error class="mt-2" :messages="$errors->get('name')" />
                        </div>

                        <div>
                            <x-input-label for="youtube_url" value="YouTube URL" />
                            <x-text-input id="youtube_url" name="youtube_url" type="url" class="mt-1 block w-full"
                                value="{{ old('youtube_url') }}" />
                            <div class="mt-1 text-sm text-gray-600">Optionnel si vous uploadez un fichier local.</div>
                            <x-input-error class="mt-2" :messages="$errors->get('youtube_url')" />
                        </div>

                        <div>
                            <x-input-label for="local_video_file" value="Local video file" />
                            <input id="local_video_file" name="local_video_file" type="file" accept="video/*"
                                class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500" />
                            <div class="mt-1 text-sm text-gray-600">Upload un fichier vidéo au lieu d’une URL YouTube.</div>
                            <x-input-error class="mt-2" :messages="$errors->get('local_video_file')" />
                        </div>

                        <div>
                            <x-input-label for="output_aspect" value="Format" />
                            <select id="output_aspect" name="output_aspect"
                                class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500">
                                <option value="vertical"
                                    {{ old('output_aspect', 'vertical') === 'vertical' ? 'selected' : '' }}>Vertical
                                    (9:16)</option>
                                <option value="source"
                                    {{ old('output_aspect', 'vertical') === 'source' ? 'selected' : '' }}>Original
                                    (YouTube)</option>
                            </select>
                            <x-input-error class="mt-2" :messages="$errors->get('output_aspect')" />
                        </div>

                        <div>
                            <x-input-label for="subtitle_template" value="Style de sous-titres" />
                            <select id="subtitle_template" name="subtitle_template"
                                class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500">
                                <option value="default"
                                    {{ old('subtitle_template', 'cinematic_karaoke') === 'default' ? 'selected' : '' }}>
                                    Default</option>
                                <option value="modern"
                                    {{ old('subtitle_template', 'cinematic_karaoke') === 'modern' ? 'selected' : '' }}>
                                    Modern</option>
                                <option value="modern_karaoke"
                                    {{ old('subtitle_template', 'cinematic_karaoke') === 'modern_karaoke' ? 'selected' : '' }}>
                                    Modern (karaoke)</option>
                                <option value="cinematic"
                                    {{ old('subtitle_template', 'cinematic_karaoke') === 'cinematic' ? 'selected' : '' }}>
                                    Cinematic</option>
                                <option value="cinematic_karaoke"
                                    {{ old('subtitle_template', 'cinematic_karaoke') === 'cinematic_karaoke' ? 'selected' : '' }}>
                                    Cinematic (karaoke)</option>
                            </select>
                            <div class="mt-1 text-sm text-gray-600">Choisissez un style (on pourra en ajouter d’autres).
                            </div>
                            <x-input-error class="mt-2" :messages="$errors->get('subtitle_template')" />
                        </div>

                        <div class="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 p-4">
                            <div>
                                <div class="text-sm font-medium text-gray-900">Mode originalité</div>
                                <div class="mt-1 text-sm text-gray-600">Ajoute un voice-over IA et peut remplacer
                                    l’audio original (réduit le risque de claims, sans garantie).</div>
                            </div>

                            <label class="inline-flex items-center gap-2">
                                <input type="checkbox" name="originality_enabled" value="1"
                                    {{ old('originality_enabled') ? 'checked' : '' }}
                                    class="rounded border-gray-300 text-indigo-600 shadow-sm focus:ring-indigo-500" />
                                <span class="text-sm text-gray-700">Activer</span>
                            </label>
                        </div>

                        <div class="flex items-center gap-3">
                            <x-primary-button>Create</x-primary-button>
                            <a href="{{ route('projects.index') }}"
                                class="text-sm text-gray-600 hover:text-gray-900">Cancel</a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>