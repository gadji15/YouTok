<?php

declare(strict_types=1);

namespace App\Enums;

enum ProjectStatus: string
{
    case queued = 'queued';
    case processing = 'processing';
    case completed = 'completed';
    case failed = 'failed';
}
