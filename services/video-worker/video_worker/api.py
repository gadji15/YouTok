from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException, Header
from rq.job import Job

from .callback import JobCallbackPayload, JobStatus, post_callback
from .config import get_settings
from .jobs import process_job
from .logging import configure_logging, get_logger
from .models import JobCreateRequest, JobCreateResponse
from .redis_conn import get_redis
from .rq_queue import get_queue

try:
    from .observability import configure_metrics, configure_sentry
except ModuleNotFoundError:

    def configure_sentry(*, dsn: str, traces_sample_rate: float = 0.0) -> None:
        return

    def configure_metrics(*, app: FastAPI) -> None:
        return


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    logger = get_logger(service="video-worker-api")

    configure_sentry(
        dsn=getattr(settings, "sentry_dsn", ""),
        traces_sample_rate=getattr(settings, "sentry_traces_sample_rate", 0.0),
    )

    app = FastAPI(title="video-worker")

    if getattr(settings, "metrics_enabled", False):
        configure_metrics(app=app)

    def require_api_key(authorization: str | None) -> None:
        if settings.api_key:
            expected = f"Bearer {settings.api_key}"
            if not authorization or authorization.strip() != expected:
                raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health")
    def health() -> dict:
        try:
            get_redis().ping()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"redis_unavailable: {e}")

        return {"status": "ok"}

    @app.post("/jobs", response_model=JobCreateResponse)
    def create_job(req: JobCreateRequest, authorization: str | None = Header(default=None)) -> JobCreateResponse:
        require_api_key(authorization)

        if not req.youtube_url and not req.local_video_path:
            raise HTTPException(status_code=422, detail="one_of_youtube_url_or_local_video_path_required")
        if req.youtube_url and req.local_video_path:
            raise HTTPException(status_code=422, detail="only_one_source_allowed")

        if settings.callback_host_allowlist:
            allowed = {h.strip() for h in settings.callback_host_allowlist.split(",") if h.strip()}
            host = getattr(req.callback_url, "host", None)
            if not host or host not in allowed:
                raise HTTPException(status_code=400, detail=f"callback_host_not_allowed: {host}")

        job_id = str(uuid4())

        queue = get_queue()
        queue.enqueue(
            process_job,
            job_id,
            req.project_id,
            str(req.youtube_url or ""),
            req.local_video_path,
            str(req.callback_url),
            req.callback_secret,
            req.language,
            req.segmentation_mode,
            req.subtitles_enabled,
            req.subtitle_template,
            req.clip_min_seconds,
            req.clip_max_seconds,
            req.max_clips,
            req.originality_mode,
            req.output_aspect,
            job_id=job_id,
            result_ttl=settings.rq_result_ttl_seconds,
        )

        try:
            post_callback(
                callback_url=str(req.callback_url),
                callback_secret=req.callback_secret,
                payload=JobCallbackPayload(
                    job_id=job_id,
                    project_id=req.project_id,
                    status=JobStatus.queued,
                ),
                timeout_seconds=settings.callback_timeout_seconds,
                max_retries=settings.callback_max_retries,
                retry_backoff_seconds=settings.callback_retry_backoff_seconds,
                logger=logger,
            )
        except Exception:
            logger.exception("callback.post_failed", status=JobStatus.queued, job_id=job_id)

        logger.info("job.enqueued", job_id=job_id, project_id=req.project_id)
        return JobCreateResponse(job_id=job_id)

    @app.delete("/jobs/{job_id}")
    def cancel_job(job_id: str, authorization: str | None = Header(default=None)) -> dict:
        require_api_key(authorization)

        # Best-effort cancellation. If the job is queued, remove it from the queue.
        # If it's already running, we set a cancel flag in Redis and rely on the worker
        # to stop at the next checkpoint.
        r = get_redis()
        r.setex(f"video-worker:cancel:{job_id}", 60 * 60, "1")

        try:
            job = Job.fetch(job_id, connection=r)
            job.cancel()
        except Exception:
            # If the job doesn't exist (already finished/cleaned), that's fine.
            pass

        return {"ok": True, "job_id": job_id}

    return app


app = create_app()
