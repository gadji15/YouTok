<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api;

use App\Models\TikTokAccount;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class TikTokAccountController
{
    public function index(Request $request): JsonResponse
    {
        $accounts = TikTokAccount::query()->orderBy('created_at')->limit(200)->get();

        return response()->json([
            'data' => $accounts->map(static function (TikTokAccount $account): array {
                return [
                    'id' => (string) $account->id,
                    'username' => $account->username,
                    'status' => $account->status->value,
                    'notes' => $account->notes,
                ];
            })->values(),
        ]);
    }
}