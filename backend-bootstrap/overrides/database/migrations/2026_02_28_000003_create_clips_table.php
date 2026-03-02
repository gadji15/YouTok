<?php

declare(strict_types=1);

use App\Enums\ClipStatus;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('clips', function (Blueprint $table) {
            $table->uuid('id')->primary();

            $table->uuid('project_id');
            $table->uuid('tiktok_account_id')->nullable();

            $table->string('external_id')->nullable();
            $table->decimal('start_seconds', 10, 3)->nullable();
            $table->decimal('end_seconds', 10, 3)->nullable();
            $table->decimal('score', 6, 4)->nullable();

            $table->string('status')->default(ClipStatus::pending->value);

            $table->string('video_path')->nullable();
            $table->string('subtitles_ass_path')->nullable();

            $table->timestamps();

            $table->foreign('project_id')->references('id')->on('projects')->cascadeOnDelete();
            $table->foreign('tiktok_account_id')->references('id')->on('tiktok_accounts')->nullOnDelete();

            $table->index(['project_id', 'external_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('clips');
    }
};
