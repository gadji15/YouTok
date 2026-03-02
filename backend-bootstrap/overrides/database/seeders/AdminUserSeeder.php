<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;

class AdminUserSeeder extends Seeder
{
    public function run(): void
    {
        $emails = config('admin.emails', []);
        if (!is_array($emails) || count($emails) === 0) {
            return;
        }

        $email = (string) $emails[0];
        if ($email === '') {
            return;
        }

        User::query()->updateOrCreate(
            ['email' => $email],
            [
                'name' => 'Admin',
                'password' => Hash::make((string) config('admin.password', 'password')),
                'email_verified_at' => now(),
            ],
        );
    }
}
