<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Str;
use Tests\TestCase;

class UploadApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_upload_requires_internal_secret(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        $file = UploadedFile::fake()->create('source.mp4', 1, 'video/mp4');

        $this->post('/api/uploads/video', [
            'video' => $file,
        ])->assertForbidden();
    }

    public function test_upload_stores_file_inside_shared_root_and_returns_path(): void
    {
        config()->set('admin.internal_api_secret', 'test-secret');

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'shared-root-'.Str::random(8);
        @mkdir($root, 0777, true);
        config()->set('admin.shared_storage_root', $root);

        $file = UploadedFile::fake()->create('source.mp4', 10, 'video/mp4');

        $res = $this->withHeader('X-Internal-Secret', 'test-secret')
            ->post('/api/uploads/video', [
                'video' => $file,
            ])
            ->assertOk()
            ->assertJsonStructure(['local_video_path', 'original_name', 'size_bytes']);

        $path = (string) $res->json('local_video_path');

        $this->assertNotSame('', $path);
        $this->assertStringContainsString($root.DIRECTORY_SEPARATOR.'storage'.DIRECTORY_SEPARATOR.'uploads', $path);
        self::assertFileExists($path);
    }
}
