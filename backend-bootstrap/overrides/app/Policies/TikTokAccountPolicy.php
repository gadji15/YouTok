<?php

declare(strict_types=1);

namespace App\Policies;

use App\Models\TikTokAccount;
use App\Models\User;
use App\Support\Admin;

class TikTokAccountPolicy
{
    public function viewAny(User $user): bool
    {
        return Admin::isAdmin($user);
    }

    public function view(User $user, TikTokAccount $account): bool
    {
        return Admin::isAdmin($user);
    }

    public function create(User $user): bool
    {
        return Admin::isAdmin($user);
    }

    public function update(User $user, TikTokAccount $account): bool
    {
        return Admin::isAdmin($user);
    }

    public function delete(User $user, TikTokAccount $account): bool
    {
        return Admin::isAdmin($user);
    }
}