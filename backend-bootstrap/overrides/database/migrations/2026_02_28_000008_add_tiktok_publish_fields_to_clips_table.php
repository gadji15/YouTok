<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('clips', function (Blueprint $table) {
            $table->string('tiktok_publish_job_id')->nullable()->after('tiktok_account_id');
            $table->string('tiktok_publish_status')->nullable()->after('tiktok_publish_job_id');
            $table->text('tiktok_publish_error')->nullable()->after('tiktok_publish_status');
            $table->text('tiktok_caption')->nullable()->after('tiktok_publish_error');
            $table->timestamp('tiktok_published_at')->nullable()->after('tiktok_caption');

            $table->index(['tiktok_publish_status']);
        });
    }

    public function down(): void
    {
        Schema::table('clips', function (Blueprint $table) {
            $table->dropIndex(['tiktok_publish_status']);
            $table->dropColumn([
                'tiktok_publish_job_id',
                'tiktok_publish_status',
                'tiktok_publish_error',
                'tiktok_caption',
                'tiktok_published_at',
            ]);
        });
    }
};