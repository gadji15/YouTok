<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\Clip;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\HttpFoundation\Response;

class ClipAssetController extends Controller
{
    public function video(Request $request, Clip $clip): Response
    {
        $this->authorize('view', $clip);

        $path = (string) ($clip->video_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveFile(
            absolutePath: $path,
            contentType: 'video/mp4',
            downloadName: ($clip->external_id ?? (string) $clip->id).'.mp4',
            inline: true,
        );
    }

    public function downloadAss(Request $request, Clip $clip): Response
    {
        $this->authorize('view', $clip);

        $path = (string) ($clip->subtitles_ass_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveFile(
            absolutePath: $path,
            contentType: 'text/plain; charset=utf-8',
            downloadName: ($clip->external_id ?? (string) $clip->id).'.ass',
            inline: false,
        );
    }

    public function downloadSrt(Request $request, Clip $clip): Response
    {
        $this->authorize('view', $clip);

        $path = (string) ($clip->subtitles_srt_path ?? '');
        if ($path === '') {
            abort(404);
        }

        return $this->serveFile(
            absolutePath: $path,
            contentType: 'text/plain; charset=utf-8',
            downloadName: ($clip->external_id ?? (string) $clip->id).'.srt',
            inline: false,
        );
    }

    private function serveFile(
        string $absolutePath,
        string $contentType,
        string $downloadName,
        bool $inline,
    ): Response {
        $path = trim($absolutePath);
        if (str_starts_with($path, 'http://') || str_starts_with($path, 'https://')) {
            return redirect()->away($path);
        }

        $real = realpath($path);
        if ($real === false || !is_file($real)) {
            abort(404);
        }

        $root = (string) config('admin.shared_storage_root', '/shared');
        $rootReal = realpath($root) ?: $root;

        // Prevent path traversal / serving arbitrary files outside the mounted shared volume.
        $rootPrefix = rtrim($rootReal, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR;
        if (!str_starts_with($real, $rootPrefix)) {
            abort(403);
        }

        $disposition = ($inline ? 'inline' : 'attachment').'; filename="'.$downloadName.'"';

        /** @var BinaryFileResponse $response */
        $response = response()->file($real, [
            'Content-Type' => $contentType,
            'Content-Disposition' => $disposition,
        ]);

        return $response;
    }
}