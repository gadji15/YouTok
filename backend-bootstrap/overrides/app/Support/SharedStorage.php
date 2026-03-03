<?php

declare(strict_types=1);

namespace App\Support;

use Illuminate\Support\Facades\File;

final class SharedStorage
{
    public static function deleteFile(?string $absolutePath): void
    {
        $path = (string) ($absolutePath ?? '');
        if ($path === '') {
            return;
        }

        $real = realpath($path);
        if ($real === false || !is_file($real)) {
            return;
        }

        $root = (string) config('admin.shared_storage_root', '/shared');
        $rootReal = realpath($root) ?: $root;

        // Prevent deleting arbitrary files outside the mounted shared volume.
        $rootPrefix = rtrim($rootReal, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR;
        if (!str_starts_with($real, $rootPrefix)) {
            return;
        }

        File::delete($real);
    }
}