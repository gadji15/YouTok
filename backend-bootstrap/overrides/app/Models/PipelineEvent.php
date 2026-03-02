<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class PipelineEvent extends Model
{
    protected $fillable = [
        'project_id',
        'clip_id',
        'type',
        'message',
        'payload',
    ];

    protected $casts = [
        'payload' => 'array',
    ];

    public static function log(
        string $type,
        ?string $message = null,
        array $payload = [],
        ?Project $project = null,
        ?Clip $clip = null,
    ): self {
        return self::create([
            'project_id' => $project?->id,
            'clip_id' => $clip?->id,
            'type' => $type,
            'message' => $message,
            'payload' => $payload === [] ? null : $payload,
        ]);
    }

    public function project(): BelongsTo
    {
        return $this->belongsTo(Project::class);
    }

    public function clip(): BelongsTo
    {
        return $this->belongsTo(Clip::class);
    }
}
