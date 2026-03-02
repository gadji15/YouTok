<?php

declare(strict_types=1);

namespace App\Support;

use App\Models\User;

final class Admin
{
    public static function isAdmin(?User $user): bool
    {
        if (!$user) {
            return false;
        }

        $emails = config('admin.emails', []);
        if (!is_array($emails) || count($emails) === 0) {
            return false;
        }

        return in_array($user->email, $emails, true);
    }
}
