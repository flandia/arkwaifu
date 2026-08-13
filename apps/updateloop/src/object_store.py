"""Store the Arkwaifu database and art objects in S3-compatible storage."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .asyncio_tools import await_owned
from .domain import PngImage

DATABASE_OBJECT_KEY = "arkwaifu.sqlite3"
_DATABASE_CONTENT_TYPE = "application/vnd.sqlite3"
_PNG_CONTENT_TYPE = "image/png"
_PNG_CACHE_CONTROL = "public, max-age=31536000, immutable"
_THUMBNAIL_CONTENT_TYPE = "image/webp"
_MAX_POOL_CONNECTIONS = 16


def _error_code(error: ClientError) -> str | None:
    """Read one S3 error code without assuming a particular provider."""

    code = error.response.get("Error", {}).get("Code")
    return code if isinstance(code, str) else None


def _is_missing(error: ClientError) -> bool:
    """Return whether a provider reported an absent object."""

    return _error_code(error) in {"404", "NoSuchKey", "NotFound"}


class ObjectStore(Protocol):
    """Pull and push the database and its art objects."""

    async def pull_database(self, destination: Path) -> bool:
        """Download the current database, returning false when it does not exist."""
        ...

    async def push_database(self, source: Path) -> None:
        """Replace the current database with the completed local file."""
        ...

    async def put_png(self, key: str, artifact: PngImage) -> None:
        """Create one immutable composition or source PNG object."""
        ...

    async def put_thumbnail(self, key: str, content: bytes) -> None:
        """Replace one derived WebP thumbnail object."""
        ...


class S3ObjectStore:
    """Store the database and art objects in one versioned S3-compatible bucket.

    The updater leaves bucket policy and lifecycle management to the operator.
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
        """Configure access to one S3-compatible bucket."""
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
            if _is_missing(error):
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
        """Create one PNG, accepting an already matching immutable object."""
        await await_owned(asyncio.to_thread(self._put_png, key, artifact))

    def _put_png(self, key: str, artifact: PngImage) -> None:
        try:
            existing = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if not _is_missing(error):
                raise
        else:
            self._validate_png(key, artifact, existing)
            return

        request = {
            "Bucket": self._bucket,
            "Key": key,
            "ContentLength": artifact.byte_size,
            "ContentType": _PNG_CONTENT_TYPE,
            "CacheControl": _PNG_CACHE_CONTROL,
        }
        if artifact.path is None:
            self._client.put_object(Body=artifact.content, **request)
        else:
            with artifact.path.open("rb") as content:
                self._client.put_object(Body=content, **request)

    async def put_thumbnail(self, key: str, content: bytes) -> None:
        """Replace one mutable WebP thumbnail."""

        await await_owned(asyncio.to_thread(self._put_thumbnail, key, content))

    def _put_thumbnail(self, key: str, content: bytes) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentLength=len(content),
            ContentType=_THUMBNAIL_CONTENT_TYPE,
        )

    @staticmethod
    def _validate_png(key: str, artifact: PngImage, metadata: dict[str, object]) -> None:
        """Require an existing object to match the immutable PNG contract."""

        expected = {
            "ContentLength": artifact.byte_size,
            "ContentType": _PNG_CONTENT_TYPE,
            "CacheControl": _PNG_CACHE_CONTROL,
        }
        mismatches = {
            name: (metadata.get(name), value)
            for name, value in expected.items()
            if metadata.get(name) != value
        }
        if mismatches:
            detail = ", ".join(
                f"{name}={actual!r} (expected {wanted!r})"
                for name, (actual, wanted) in mismatches.items()
            )
            raise ValueError(f"immutable PNG object conflicts with {key}: {detail}")


class MemoryObjectStore:
    """Store database and art bytes in memory for deterministic updater tests."""

    def __init__(self) -> None:
        """Create an empty in-memory object store."""
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
        """Create one immutable PNG or accept an identical existing value."""

        content = artifact.content
        existing = self.objects.setdefault(key, content)
        if existing != content:
            raise ValueError(f"immutable PNG object conflicts with {key}")

    async def put_thumbnail(self, key: str, content: bytes) -> None:
        """Replace one mutable WebP thumbnail."""

        self.objects[key] = content
