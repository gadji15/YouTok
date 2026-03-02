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
            $table->string('source_video_path')->nullable()->after('worker_job_id');
            $table->string('audio_path')->nullable()->after('source_video_path');
            $table->string('transcript_json_path')->nullable()->after('audio_path');
            $table->string('subtitles_srt_path')->nullable()->after('transcript_json_path');
            $table->string('clips_json_path')->nullable()->after('subtitles_srt_path');
            $table->text('error')->nullable()->after('clips_json_path');
        });
    }

    public function down(): void
    {
        Schema::table('projects', function (Blueprint $table) {
            $table->dropColumn([
                'source_video_path',
                'audio_path',
                'transcript_json_path',
                'subtitles_srt_path',
                'clips_json_path',
                'error',
            ]);
        });
    }
};
