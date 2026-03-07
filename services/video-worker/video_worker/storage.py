from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import get_settings


@dataclass(frozen=True)
class S3Config:
    bucket: str
    prefix: str
    region: str
    endpoint_url: str
    public_base_url: str
    access_key_id: str
    secret_access_key: str


def get_s3_config() -> S3Config | None:
    """Return S3 config when enabled.

    This is intentionally "prep" only: the current app still uses local /shared paths.
    We expose a single place to read configuration so that later we can:
    - upload rendered artifacts
    - store S3 URLs alongside local paths
    - serve artifacts via signed URLs
    """

    s = get_settings()
    if not s.s3_bucket:
        return None

    return S3Config(
        bucket=s.s3_bucket,
        prefix=s.s3_prefix,
        region=s.s3_region,
        endpoint_url=s.s3_endpoint_url,
        public_base_url=s.s3_public_base_url,
        access_key_id=s.s3_access_key_id,
        secret_access_key=s.s3_secret_access_key,
    )


def s3_enabled() -> bool:
    return get_s3_config() is not None


def upload_file_to_s3(*, local_path: Path, key: str) -> str:
    """Upload a file to S3 and return its s3:// or https URL.

    Not wired into the pipeline yet. This function is provided so the pipeline can
    start emitting S3 URLs in a later iteration.

    Requires optional dependency: boto3.
    """

    cfg = get_s3_config()
    if cfg is None:
        raise RuntimeError("S3 is not configured (VIDEO_WORKER_S3_BUCKET is empty)")

    try:
        import boto3
    except ModuleNotFoundError as e:
        raise RuntimeError("boto3 is required for S3 uploads") from e

    session = boto3.session.Session(
        aws_access_key_id=cfg.access_key_id or None,
        aws_secret_access_key=cfg.secret_access_key or None,
        region_name=cfg.region or None,
    )

    from botocore.config import Config

    client = session.client(
        "s3",
        endpoint_url=cfg.endpoint_url or None,
        config=Config(
            connect_timeout=10,
            read_timeout=300,
            retries={
                "max_attempts": 3,
                "mode": "standard",
            },
            max_pool_connections=10,
        ),
    )

    client.upload_file(
        Filename=str(local_path),
        Bucket=cfg.bucket,
        Key=key,
    )

    if cfg.public_base_url:
        return f"{cfg.public_base_url.rstrip('/')}/{key}"

    # Basic URL form (provider dependent). For AWS, this is typically valid.
    if cfg.endpoint_url:
        return f"{cfg.endpoint_url.rstrip('/')}/{cfg.bucket}/{key}"

    return f"https://{cfg.bucket}.s3.amazonaws.com/{key}"
