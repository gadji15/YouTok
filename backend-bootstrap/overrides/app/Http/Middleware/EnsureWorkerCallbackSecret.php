<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class EnsureWorkerCallbackSecret
{
    public function handle(Request $request, Closure $next)
    {
        $expected = (string) config('admin.video_worker_callback_secret', '');

        if (app()->environment('production') && ($expected === '' || $expected === 'change-me-too' || str_starts_with($expected, 'please-change'))) {
            abort(500, 'VIDEO_WORKER_CALLBACK_SECRET is not configured');
        }

        $provided = (string) $request->header('X-Callback-Secret', '');
        if ($provided === '') {
            $provided = (string) $request->input('callback_secret', '');
        }

        if ($expected === '' || $provided === '' || !hash_equals($expected, $provided)) {
            abort(403);
        }

        return $next($request);
    }
}
