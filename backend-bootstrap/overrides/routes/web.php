<?php

declare(strict_types=1);

use App\Http\Controllers\ClipAssetController;
use App\Http\Controllers\ClipController;
use App\Http\Controllers\ClipPublishController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\ProfileController;
use App\Http\Controllers\ProjectAssetController;
use App\Http\Controllers\ProjectController;
use App\Http\Controllers\TikTokAccountController;
use Illuminate\Support\Facades\Route;

Route::view('/', 'welcome');

Route::get('/dashboard', [DashboardController::class, 'index'])
    ->middleware(['auth', 'verified', 'admin'])
    ->name('dashboard');

Route::middleware('auth')->group(function () {
    Route::get('/profile', [ProfileController::class, 'edit'])->name('profile.edit');
    Route::patch('/profile', [ProfileController::class, 'update'])->name('profile.update');
    Route::delete('/profile', [ProfileController::class, 'destroy'])->name('profile.destroy');
});

Route::middleware(['auth', 'verified', 'admin'])->group(function () {
    Route::get('/projects', [ProjectController::class, 'index'])->name('projects.index');
    Route::get('/projects/create', [ProjectController::class, 'create'])->name('projects.create');
    Route::post('/projects', [ProjectController::class, 'store'])->name('projects.store');
    Route::get('/projects/{project}/status', [ProjectController::class, 'status'])->name('projects.status');
    Route::get('/projects/{project}', [ProjectController::class, 'show'])->name('projects.show');
    Route::delete('/projects/{project}', [ProjectController::class, 'destroy'])->name('projects.destroy');

    // Secure serving of project artifacts stored in the shared volume.
    Route::get('/projects/{project}/artifacts/transcript.json', [ProjectAssetController::class, 'transcriptJson'])->name('projects.artifacts.transcript');
    Route::get('/projects/{project}/artifacts/subtitles.srt', [ProjectAssetController::class, 'subtitlesSrt'])->name('projects.artifacts.subtitles');
    Route::get('/projects/{project}/artifacts/clips.json', [ProjectAssetController::class, 'clipsJson'])->name('projects.artifacts.clips');

    Route::get('/clips/{clip}', [ClipController::class, 'show'])->name('clips.show');

    Route::post('/clips/{clip}/publish', [ClipPublishController::class, 'publish'])->name('clips.publish');
    Route::get('/clips/{clip}/publish/status', [ClipPublishController::class, 'status'])->name('clips.publish.status');

    // Secure serving of generated artifacts stored in the shared volume.
    Route::get('/clips/{clip}/video', [ClipAssetController::class, 'video'])->name('clips.video');
    Route::get('/clips/{clip}/subtitles.ass', [ClipAssetController::class, 'downloadAss'])->name('clips.subtitles.ass');
    Route::get('/clips/{clip}/subtitles.srt', [ClipAssetController::class, 'downloadSrt'])->name('clips.subtitles.srt');

    // TikTok accounts
    Route::get('/tiktok-accounts', [TikTokAccountController::class, 'index'])->name('tiktok-accounts.index');
    Route::get('/tiktok-accounts/create', [TikTokAccountController::class, 'create'])->name('tiktok-accounts.create');
    Route::post('/tiktok-accounts', [TikTokAccountController::class, 'store'])->name('tiktok-accounts.store');
    Route::get('/tiktok-accounts/{tiktokAccount}/edit', [TikTokAccountController::class, 'edit'])->name('tiktok-accounts.edit');
    Route::put('/tiktok-accounts/{tiktokAccount}', [TikTokAccountController::class, 'update'])->name('tiktok-accounts.update');
    Route::delete('/tiktok-accounts/{tiktokAccount}', [TikTokAccountController::class, 'destroy'])->name('tiktok-accounts.destroy');
});

require __DIR__.'/auth.php';