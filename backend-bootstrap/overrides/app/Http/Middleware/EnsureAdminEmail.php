<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class EnsureAdminEmail
{
    public function handle(Request $request, Closure $next)
    {
        $user = $request->user();
        $emails = config('admin.emails', []);

        if (!$user || !is_array($emails) || !in_array($user->email, $emails, true)) {
            abort(403);
        }

        return $next($request);
    }
}
