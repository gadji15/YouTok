<?php

declare(strict_types=1);

namespace App\Support;

use Illuminate\Support\Facades\File;

final class SharedStorage
{
    public static function resolveFileWithinRoot(string $absolutePath): ?string
    {
        $path = trim($absolutePath);
        if ($path === '') {
            return null;
        }

        $real = realpath($path);
        if ($real === false || !is_file($real)) {
            return null;
        }

        $root = (string) config('admin.shared_storage_root', '/shared');
        $rootReal = realpath($root) ?: $root;

        // Prevent accessing arbitrary files outside the mounted shared volume.
        $rootPrefix = rtrim($rootReal, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR;
        if (!str_starts_with($real, $rootPrefix)) {
            return null;
        }

        return $real;
    }

    public static function deleteFile(?string $absolutePath): void
    {
        $path = (string) ($absolutePath ?? '');
        if ($path === '') {
            return;
        }

        $real = self::resolveFileWithinRoot($path);
        if ($real === null) {
            return;
        }

        File::delete($real);
    }
}