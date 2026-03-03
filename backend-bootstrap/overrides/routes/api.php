<?php

declare(strict_types=1);

use App\Http\Controllers\Api\ProjectController;
use App\Http\Controllers\Api\WorkerCallbackController;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

Route::middleware('auth:sanctum')->get('/user', function (Request $request) {
    return $request->user();
});

Route::middleware('internal.secret')->get('/projects', [ProjectController::class, 'index']);
Route::middleware('internal.secret')->post('/projects', [ProjectController::class, 'store']);
Route::middleware('internal.secret')->get('/projects/{project}', [ProjectController::class, 'show']);

Route::middleware('internal.secret')->get('/projects/{project}/artifacts/transcript', [\App\Http\Controllers\Api\ProjectAssetController::class, 'transcriptJson']);
Route::middleware('internal.secret')->get('/projects/{project}/artifacts/subtitles', [\App\Http\Controllers\Api\ProjectAssetController::class, 'subtitlesSrt']);
Route::middleware('internal.secret')->get('/projects/{project}/artifacts/clips', [\App\Http\Controllers\Api\ProjectAssetController::class, 'clipsJson']);

Route::middleware('internal.secret')->get('/clips', [\App\Http\Controllers\Api\ClipController::class, 'index']);
Route::middleware('internal.secret')->get('/clips/{clip}', [\App\Http\Controllers\Api\ClipController::class, 'show']);
Route::middleware('internal.secret')->delete('/clips/{clip}', [\App\Http\Controllers\Api\ClipController::class, 'destroy']);
Route::middleware('internal.secret')->get('/clips/{clip}/video', [\App\Http\Controllers\Api\ClipAssetController::class, 'video']);
Route::middleware('internal.secret')->get('/clips/{clip}/subtitles.srt', [\App\Http\Controllers\Api\ClipAssetController::class, 'downloadSrt']);
Route::middleware('internal.secret')->get('/clips/{clip}/subtitles.ass', [\App\Http\Controllers\Api\ClipAssetController::class, 'downloadAss']);

Route::middleware('worker.callback')->post('/worker/callback', [WorkerCallbackController::class, 'store']);
