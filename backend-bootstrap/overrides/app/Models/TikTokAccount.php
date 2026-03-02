<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\TikTokAccountStatus;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class TikTokAccount extends Model
{
    use HasUuids;

    protected $table = 'tiktok_accounts';

    protected $fillable = [
        'username',
        'status',
        'notes',
    ];

    protected $casts = [
        'status' => TikTokAccountStatus::class,
    ];

    public function clips(): HasMany
    {
        return $this->hasMany(Clip::class);
    }
}