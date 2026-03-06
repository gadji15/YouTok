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
            $table->string('language', 8)->nullable()->after('youtube_url');
            $table->boolean('subtitles_enabled')->default(true)->after('language');
            $table->unsignedSmallInteger('clip_min_seconds')->default(60)->after('subtitles_enabled');
            $table->unsignedSmallInteger('clip_max_seconds')->default(180)->after('clip_min_seconds');
            $table->string('subtitle_template', 32)->nullable()->after('clip_max_seconds');
        });
    }

    public function down(): void
    {
        Schema::table('projects', function (Blueprint $table) {
            $table->dropColumn([
                'language',
                'subtitles_enabled',
                'clip_min_seconds',
                'clip_max_seconds',
                'subtitle_template',
            ]);
        });
    }
};
