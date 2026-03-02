<?php

declare(strict_types=1);

namespace App\Enums;

enum ClipStatus: string 
{
    case pending = 'pending';
    case ready = 'ready';
    case failed = 'failed';
}