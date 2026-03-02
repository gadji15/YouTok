from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException, Header

from .callback import JobCallbackPayload, JobStatus, post_callback
from .config import get_settings
from .jobs import process_job
from .logging import configure_logging, get_logger
from .models import JobCreateRequest, JobCreateResponse
from .observability import configure_metrics, configure_sentry
from .redis_conn import get_redis
from .rq_queue import get_queue


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    logger = get_logger(service="video-worker-api")

    configure_sentry(dsn=settings.sentry_dsn, traces_sample_rate=settings.sentry_traces_sample_rate)

    app = FastAPI(title="video-worker")

    if settings.metrics_enabled:
        configure_metrics(app=app)

    @app.get("/health")
    def health() -> dict:
        try:
            get_redis().ping()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"redis_unavailable: {e}")

        return {"status": "ok"}

    @app.post("/jobs", response_model=JobCreateResponse)
    def create_job(req: JobCreateRequest, authorization: str | None = Header(default=None)) -> JobCreateResponse:
        if settings.api_key:
            expected = f"Bearer {settings.api_key}"
            if not authorization or authorization.strip() != expected:
                raise HTTPException(status_code=401, detail="unauthorized")

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
            str(req.youtube_url),
            str(req.callback_url),
            req.callback_secret,
            req.language,
            req.subtitles_enabled,
            req.subtitle_template,
            req.clip_min_seconds,
            req.clip_max_seconds,
            req.max_clips,
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

    return app


app = create_app()
