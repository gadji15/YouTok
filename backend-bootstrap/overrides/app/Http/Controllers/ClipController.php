<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Enums\TikTokAccountStatus;
use App\Models\Clip;
use App\Models\TikTokAccount;
use Illuminate\View\View;

class ClipController extends Controller
{
    public function show(Clip $clip): View
    {
        $this->authorize('view', $clip);

        $clip->load([
            'project',
            'pipelineEvents' => fn ($q) => $q->orderByDesc('created_at')->limit(50),
        ]);

        $tiktokAccounts = TikTokAccount::query()
            ->where('status', TikTokAccountStatus::active->value)
            ->orderBy('name')
            ->get();

        return view('clips.show', [
            'clip' => $clip,
            'events' => $clip->pipelineEvents,
            'tiktokAccounts' => $tiktokAccounts,
        ]);
    }
}