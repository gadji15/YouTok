<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Enums\ProjectStatus;
use App\Models\PipelineEvent;
use App\Models\Project;
use Illuminate\View\View;

class DashboardController extends Controller
{
    public function index(): View
    {
        $this->authorize('viewAny', Project::class);

        $counts = [
            'queued' => Project::query()->where('status', ProjectStatus::queued)->count(),
            'processing' => Project::query()->where('status', ProjectStatus::processing)->count(),
            'completed' => Project::query()->where('status', ProjectStatus::completed)->count(),
            'failed' => Project::query()->where('status', ProjectStatus::failed)->count(),
        ];

        $projects = Project::query()->orderByDesc('created_at')->limit(10)->get();

        $events = PipelineEvent::query()
            ->with(['project'])
            ->orderByDesc('created_at')
            ->limit(20)
            ->get();

        return view('dashboard', [
            'counts' => $counts,
            'projects' => $projects,
            'events' => $events,
        ]);
    }
}
