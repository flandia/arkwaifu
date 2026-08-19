"""Load updater configuration from the process environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"required environment variable is not set: {name}")
    return value


def _boolean(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw!r}")


def _positive_integer(name: str, *, default: int | None = None) -> int | None:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer, got {raw!r}") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {raw!r}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Contain the remote endpoints, credentials, and concurrency limits for one run."""

    s3_endpoint_url: str | None
    s3_region: str
    s3_bucket: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_path_style: bool
    archive_s3_endpoint_url: str
    archive_s3_region: str
    archive_s3_bucket: str
    archive_s3_path_style: bool
    artwork_version_url: str
    artwork_asset_base_url: str
    github_api_url: str
    github_token: str | None
    download_workers: int
    extraction_workers: int | None

    @classmethod
    def from_environment(cls) -> Settings:
        """Load settings, rejecting absent credentials and invalid worker limits."""

        return cls(
            s3_endpoint_url=os.environ.get("ARKWAIFU_S3_ENDPOINT_URL"),
            s3_region=os.environ.get("ARKWAIFU_S3_REGION", "us-east-1"),
            s3_bucket=_required("ARKWAIFU_S3_BUCKET"),
            s3_access_key_id=_required("ARKWAIFU_S3_ACCESS_KEY_ID"),
            s3_secret_access_key=_required("ARKWAIFU_S3_SECRET_ACCESS_KEY"),
            s3_path_style=_boolean("ARKWAIFU_S3_PATH_STYLE", default=False),
            archive_s3_endpoint_url=os.environ.get(
                "ARKWAIFU_ARCHIVE_S3_ENDPOINT_URL",
                "https://sgp1.digitaloceanspaces.com",
            ).rstrip("/"),
            archive_s3_region=os.environ.get("ARKWAIFU_ARCHIVE_S3_REGION", "sgp1"),
            archive_s3_bucket=os.environ.get(
                "ARKWAIFU_ARCHIVE_S3_BUCKET",
                "arkwaifu-ab",
            ),
            archive_s3_path_style=_boolean(
                "ARKWAIFU_ARCHIVE_S3_PATH_STYLE",
                default=False,
            ),
            artwork_version_url=os.environ.get(
                "ARKWAIFU_ARTWORK_VERSION_URL",
                "https://ak-conf.hypergryph.com/config/prod/official/Windows/version",
            ),
            artwork_asset_base_url=os.environ.get(
                "ARKWAIFU_ARTWORK_ASSET_BASE_URL",
                "https://ak.hycdn.cn/assetbundle/official/Windows/assets",
            ).rstrip("/"),
            github_api_url=os.environ.get(
                "ARKWAIFU_GITHUB_API_URL", "https://api.github.com"
            ).rstrip("/"),
            github_token=os.environ.get("ARKWAIFU_GITHUB_TOKEN"),
            download_workers=_positive_integer("ARKWAIFU_DOWNLOAD_WORKERS", default=16),
            extraction_workers=_positive_integer("ARKWAIFU_EXTRACTION_WORKERS"),
        )
