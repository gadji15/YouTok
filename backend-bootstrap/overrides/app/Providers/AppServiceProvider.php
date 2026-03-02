<?php

declare(strict_types=1);

namespace App\Providers;

use App\Models\Clip;
use App\Models\Project;
use App\Policies\ClipPolicy;
use App\Policies\ProjectPolicy;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
    }

    public function boot(): void
    {
        Gate::policy(Project::class, ProjectPolicy::class);
        Gate::policy(Clip::class, ClipPolicy::class);
    }
}
