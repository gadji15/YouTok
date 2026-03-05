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
            $table->string('words_json_path')->nullable()->after('clips_json_path');
            $table->string('segments_json_path')->nullable()->after('words_json_path');
            $table->string('source_metadata_json_path')->nullable()->after('segments_json_path');
            $table->string('source_thumbnail_path')->nullable()->after('source_metadata_json_path');
        });
    }

    public function down(): void
    {
        Schema::table('projects', function (Blueprint $table) {
            $table->dropColumn([
                'words_json_path',
                'segments_json_path',
                'source_metadata_json_path',
                'source_thumbnail_path',
            ]);
        });
    }
};
