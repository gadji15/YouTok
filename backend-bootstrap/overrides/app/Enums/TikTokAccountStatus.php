<?php

declare(strict_types=1);

namespace App\Enums;

enum TikTokAccountStatus: string
{
    case active = 'active';
    case disabled = 'disabled';
    case banned = 'banned';
}
