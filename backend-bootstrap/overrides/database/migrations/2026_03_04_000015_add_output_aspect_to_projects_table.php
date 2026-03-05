<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (Schema::hasColumn('projects', 'output_aspect')) {
            return;
        }

        Schema::table('projects', function (Blueprint $table) {
            // Keep ordering stable across environments: avoid `after(...)` because a
            // previous migration history may not include the referenced column.
            $table->string('output_aspect', 16)->default('vertical');
        });
    }

    public function down(): void
    {
        if (!Schema::hasColumn('projects', 'output_aspect')) {
            return;
        }

        Schema::table('projects', function (Blueprint $table) {
            $table->dropColumn(['output_aspect']);
        });
    }
};