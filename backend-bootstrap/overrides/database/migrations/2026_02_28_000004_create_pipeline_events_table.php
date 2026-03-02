<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('pipeline_events', function (Blueprint $table) {
            $table->id();

            $table->uuid('project_id')->nullable();
            $table->uuid('clip_id')->nullable();

            $table->string('type');
            $table->text('message')->nullable();
            $table->json('payload')->nullable();

            $table->timestamps();

            $table->foreign('project_id')->references('id')->on('projects')->nullOnDelete();
            $table->foreign('clip_id')->references('id')->on('clips')->nullOnDelete();

            $table->index(['project_id', 'created_at']);
            $table->index(['clip_id', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('pipeline_events');
    }
};
