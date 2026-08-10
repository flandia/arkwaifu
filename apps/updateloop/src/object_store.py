"""Store the Arkwaifu database and PNG objects in S3-compatible storage."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError

from .asyncio_tools import await_owned
from .domain import PngImage

DATABASE_OBJECT_KEY = "arkwaifu.sqlite3"
_DATABASE_CONTENT_TYPE = "application/vnd.sqlite3"
_PNG_CACHE_CONTROL = "public, max-age=300"
_MAX_POOL_CONNECTIONS = 16
_PNG_TRANSFER_CONFIG = TransferConfig(use_threads=False)


class ObjectStore(Protocol):
    """Pull and push the database and its PNG objects."""

    async def pull_database(self, destination: Path) -> bool:
        """Download the current database, returning false when it does not exist."""
        ...

    async def push_database(self, source: Path) -> None:
        """Replace the current database with the completed local file."""
        ...

    async def put_png(self, key: str, artifact: PngImage) -> None:
        """Upload one composition or source PNG under its version-scoped key."""
        ...


class S3ObjectStore:
    """Store database and PNG objects in one S3-compatible bucket.

    The bucket must have versioning enabled before this adapter is used.
    Versioning retains overwritten databases; the updater deliberately does
    not manage bucket policy or lifecycle.
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None = None,
        path_style: bool = False,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
            config=Config(
                max_pool_connections=_MAX_POOL_CONNECTIONS,
                s3={"addressing_style": "path" if path_style else "virtual"},
            ),
        )

    async def pull_database(self, destination: Path) -> bool:
        """Download the current database if it exists."""
        return await await_owned(asyncio.to_thread(self._pull_database, destination))

    def _pull_database(self, destination: Path) -> bool:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._client.download_file(self._bucket, DATABASE_OBJECT_KEY, str(destination))
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                destination.unlink(missing_ok=True)
                return False
            raise
        return True

    async def push_database(self, source: Path) -> None:
        """Upload the completed database as the current database."""
        await await_owned(asyncio.to_thread(self._push_database, source))

    def _push_database(self, source: Path) -> None:
        self._client.upload_file(
            str(source),
            self._bucket,
            DATABASE_OBJECT_KEY,
            ExtraArgs={
                "ContentType": _DATABASE_CONTENT_TYPE,
                "CacheControl": "no-cache",
            },
        )

    async def put_png(self, key: str, artifact: PngImage) -> None:
        """Upload one composition or source PNG."""
        await await_owned(asyncio.to_thread(self._put_png, key, artifact))

    def _put_png(self, key: str, artifact: PngImage) -> None:
        extra_args = {
            "ContentType": "image/png",
            "CacheControl": _PNG_CACHE_CONTROL,
        }
        if artifact.path is not None:
            self._client.upload_file(
                str(artifact.path),
                self._bucket,
                key,
                ExtraArgs=extra_args,
                Config=_PNG_TRANSFER_CONFIG,
            )
            return
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=artifact.content,
            **extra_args,
        )


class MemoryObjectStore:
    """Store database and PNG bytes in memory for deterministic updater tests."""

    def __init__(self) -> None:
        self.database: bytes | None = None
        self.objects: dict[str, bytes] = {}

    async def pull_database(self, destination: Path) -> bool:
        """Copy the current in-memory database to a local file."""
        if self.database is None:
            destination.unlink(missing_ok=True)
            return False
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.database)
        return True

    async def push_database(self, source: Path) -> None:
        """Replace the in-memory database with a local file."""
        self.database = source.read_bytes()

    async def put_png(self, key: str, artifact: PngImage) -> None:
        """Store one PNG under its public object key."""
        # Model only the current object value. Production S3 bucket versioning,
        # not this deterministic test adapter, retains overwritten versions.
        self.objects[key] = artifact.content
