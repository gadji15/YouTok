<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;

class UploadController
{
    public function video(Request $request): JsonResponse
    {
        $request->validate([
            'video' => ['required', 'file'],
        ]);

        /** @var \Illuminate\Http\UploadedFile|null $file */
        $file = $request->file('video');
        if ($file === null) {
            throw ValidationException::withMessages(['video' => ['missing_file']]);
        }

        $root = (string) config('admin.shared_storage_root', '/shared');
        $destDir = rtrim($root, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR.'storage'.DIRECTORY_SEPARATOR.'uploads';

        if (!is_dir($destDir) && !@mkdir($destDir, 0777, true) && !is_dir($destDir)) {
            throw new \RuntimeException('failed_to_create_upload_dir');
        }

        $ext = strtolower((string) $file->getClientOriginalExtension());
        if ($ext === '' || !preg_match('/^[a-z0-9]{1,8}$/', $ext)) {
            $ext = 'mp4';
        }

        $filename = 'upload_'.(string) Str::uuid().'.'.$ext;
        $file->move($destDir, $filename);

        $absolutePath = $destDir.DIRECTORY_SEPARATOR.$filename;

        return response()->json([
            'local_video_path' => $absolutePath,
            'original_name' => $file->getClientOriginalName(),
            'size_bytes' => $file->getSize(),
        ]);
    }
}
