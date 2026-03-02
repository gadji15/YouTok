<?php

declare(strict_types=1);

namespace App\Policies;

use App\Models\Clip;
use App\Models\User;
use App\Support\Admin;

class ClipPolicy
{
    public function view(User $user, Clip $clip): bool
    {
        return Admin::isAdmin($user);
    }
}
