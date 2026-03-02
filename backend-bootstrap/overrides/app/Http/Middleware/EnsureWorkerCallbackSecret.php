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
