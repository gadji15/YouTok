<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\Project;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

class ProjectAssetController extends Controller
{
    public function transcriptJson(Request $request, Project $project): BinaryFileResponse
    {
        $this->authorize('view', $project);

        $path = (string) ($project->transcript_json_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveLocalFile(
            absolutePath: $path,
            contentType: 'application/json; charset=utf-8',
            downloadName: 'transcript.json',
        );
    }

    public function subtitlesSrt(Request $request, Project $project): BinaryFileResponse
    {
        $this->authorize('view', $project);

        $path = (string) ($project->subtitles_srt_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveLocalFile(
            absolutePath: $path,
            contentType: 'text/plain; charset=utf-8',
            downloadName: 'subtitles.srt',
        );
    }

    public function clipsJson(Request $request, Project $project): BinaryFileResponse
    {
        $this->authorize('view', $project);

        $path = (string) ($project->clips_json_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveLocalFile(
            absolutePath: $path,
            contentType: 'application/json; charset=utf-8',
            downloadName: 'clips.json',
        );
    }

    public function wordsJson(Request $request, Project $project): BinaryFileResponse
    {
        $this->authorize('view', $project);

        $path = (string) ($project->words_json_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveLocalFile(
            absolutePath: $path,
            contentType: 'application/json; charset=utf-8',
            downloadName: 'words.json',
        );
    }

    public function segmentsJson(Request $request, Project $project): BinaryFileResponse
    {
        $this->authorize('view', $project);

        $path = (string) ($project->segments_json_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveLocalFile(
            absolutePath: $path,
            contentType: 'application/json; charset=utf-8',
            downloadName: 'segments.json',
        );
    }

    public function sourceMetadataJson(Request $request, Project $project): BinaryFileResponse
    {
        $this->authorize('view', $project);

        $path = (string) ($project->source_metadata_json_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveLocalFile(
            absolutePath: $path,
            contentType: 'application/json; charset=utf-8',
            downloadName: 'source_metadata.json',
        );
    }

    public function sourceThumbnail(Request $request, Project $project): BinaryFileResponse
    {
        $this->authorize('view', $project);

        $path = (string) ($project->source_thumbnail_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveLocalFile(
            absolutePath: $path,
            contentType: 'image/jpeg',
            downloadName: 'thumbnail.jpg',
        );
    }

    private function serveLocalFile(
        string $absolutePath,
        string $contentType,
        string $downloadName,
    ): BinaryFileResponse {
        $real = realpath($absolutePath);
        if ($real === false || !is_file($real)) {
            abort(404);
        }

        $root = (string) config('admin.shared_storage_root', '/shared');
        $rootReal = realpath($root) ?: $root;

        $rootPrefix = rtrim($rootReal, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR;
        if (!str_starts_with($real, $rootPrefix)) {
            abort(403);
        }

        /** @var BinaryFileResponse $response */
        $response = response()->file($real, [
            'Content-Type' => $contentType,
            'Content-Disposition' => 'attachment; filename="'.$downloadName.'"',
        ]);

        return $response;
    }
}