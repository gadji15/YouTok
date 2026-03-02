<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class EnsureInternalSecret
{
    public function handle(Request $request, Closure $next)
    {
        $expected = (string) config('admin.internal_api_secret', '');
        $provided = (string) $request->header('X-Internal-Secret', '');

        if ($expected === '' || $provided === '' || !hash_equals($expected, $provided)) {
            abort(403);
        }

        return $next($request);
    }
}
