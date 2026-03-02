<?php

declare(strict_types=1);

namespace App\Policies;

use App\Models\Project;
use App\Models\User;
use App\Support\Admin;

class ProjectPolicy
{
    public function viewAny(User $user): bool
    {
        return Admin::isAdmin($user);
    }

    public function view(User $user, Project $project): bool
    {
        return Admin::isAdmin($user);
    }

    public function create(User $user): bool
    {
        return Admin::isAdmin($user);
    }

    public function delete(User $user, Project $project): bool
    {
        return Admin::isAdmin($user);
    }
}
