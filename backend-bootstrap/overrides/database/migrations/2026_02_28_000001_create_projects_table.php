<?php

declare(strict_types=1);

use App\Enums\ProjectStatus;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('projects', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->string('name');

            // Sources (Part 2): YouTube URL or local file.
            $table->string('source_type', 16)->default('youtube');
            $table->string('youtube_url')->nullable();
            $table->string('local_video_path')->nullable();

            $table->string('status')->default(ProjectStatus::queued->value);
            $table->string('worker_job_id')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('projects');
    }
};
