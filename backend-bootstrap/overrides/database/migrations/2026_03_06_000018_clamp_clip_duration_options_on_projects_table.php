<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (!Schema::hasTable('projects')) {
            return;
        }

        // Clamp existing projects to the new product constraints.
        DB::table('projects')->where('clip_min_seconds', '<', 60)->update(['clip_min_seconds' => 60]);

        DB::table('projects')
            ->where('clip_max_seconds', '<', 60)
            ->orWhere('clip_max_seconds', '>', 180)
            ->update(['clip_max_seconds' => 180]);

        // Ensure clip_max_seconds >= clip_min_seconds.
        $rows = DB::table('projects')->select(['id', 'clip_min_seconds', 'clip_max_seconds'])->get();
        foreach ($rows as $row) {
            if ((int) $row->clip_max_seconds < (int) $row->clip_min_seconds) {
                DB::table('projects')->where('id', $row->id)->update([
                    'clip_max_seconds' => (int) $row->clip_min_seconds,
                ]);
            }
        }
    }

    public function down(): void
    {
        // no-op
    }
};
