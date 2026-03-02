<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Enums\TikTokAccountStatus;
use App\Models\TikTokAccount;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

class TikTokAccountController extends Controller
{
    public function index(): View
    {
        $this->authorize('viewAny', TikTokAccount::class);

        $accounts = TikTokAccount::query()->orderBy('created_at')->paginate(50);

        return view('tiktok_accounts.index', [
            'accounts' => $accounts,
        ]);
    }

    public function create(): View
    {
        $this->authorize('create', TikTokAccount::class);

        return view('tiktok_accounts.create');
    }

    public function store(Request $request): RedirectResponse
    {
        $this->authorize('create', TikTokAccount::class);

        $data = $request->validate([
            'username' => ['required', 'string', 'max:255', 'unique:tiktok_accounts,username'],
            'status' => ['required', 'string'],
            'notes' => ['sometimes', 'nullable', 'string'],
        ]);

        $status = TikTokAccountStatus::tryFrom($data['status'] ?? '') ?? TikTokAccountStatus::active;

        TikTokAccount::query()->create([
            'username' => $data['username'],
            'status' => $status,
            'notes' => $data['notes'] ?? null,
        ]);

        return redirect()->route('tiktok-accounts.index')->with('status', 'TikTok account created.');
    }

    public function edit(TikTokAccount $tiktokAccount): View
    {
        $this->authorize('update', $tiktokAccount);

        return view('tiktok_accounts.edit', [
            'account' => $tiktokAccount,
            'statuses' => TikTokAccountStatus::cases(),
        ]);
    }

    public function update(Request $request, TikTokAccount $tiktokAccount): RedirectResponse
    {
        $this->authorize('update', $tiktokAccount);

        $data = $request->validate([
            'username' => ['required', 'string', 'max:255', 'unique:tiktok_accounts,username,'.$tiktokAccount->id],
            'status' => ['required', 'string'],
            'notes' => ['sometimes', 'nullable', 'string'],
        ]);

        $status = TikTokAccountStatus::tryFrom($data['status'] ?? '') ?? TikTokAccountStatus::active;

        $tiktokAccount->forceFill([
            'username' => $data['username'],
            'status' => $status,
            'notes' => $data['notes'] ?? null,
        ])->save();

        return redirect()->route('tiktok-accounts.index')->with('status', 'TikTok account updated.');
    }

    public function destroy(TikTokAccount $tiktokAccount): RedirectResponse
    {
        $this->authorize('delete', $tiktokAccount);

        $tiktokAccount->delete();

        return redirect()->route('tiktok-accounts.index')->with('status', 'TikTok account deleted.');
    }
}