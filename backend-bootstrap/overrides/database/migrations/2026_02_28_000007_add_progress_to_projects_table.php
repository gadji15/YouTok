<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('projects', function (Blueprint $table) {
            $table->string('stage')->nullable()->after('status');
            $table->unsignedTinyInteger('progress_percent')->nullable()->after('stage');
            $table->text('last_log_message')->nullable()->after('progress_percent');
        });
    }

    public function down(): void
    {
        Schema::table('projects', function (Blueprint $table) {
            $table->dropColumn(['stage', 'progress_percent', 'last_log_message']);
        });
    }
};
