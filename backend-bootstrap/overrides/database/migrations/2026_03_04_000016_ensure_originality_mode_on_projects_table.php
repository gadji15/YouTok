<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (Schema::hasColumn('projects', 'originality_mode')) {
            return;
        }

        Schema::table('projects', function (Blueprint $table) {
            $table->string('originality_mode', 32)->default('none');
        });
    }

    public function down(): void
    {
        if (!Schema::hasColumn('projects', 'originality_mode')) {
            return;
        }

        Schema::table('projects', function (Blueprint $table) {
            $table->dropColumn(['originality_mode']);
        });
    }
};
