"""Store the Arkwaifu database and archive assets in S3-compatible storage."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import uuid
from contextlib import closing
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .asyncio_tools import await_owned
from .domain import FileAudioArtifact, FileVideoArtifact, PngImage
from .upstream.cache import UpstreamCache

DATABASE_OBJECT_KEY = "arkwaifu.sqlite3"
_DATABASE_CONTENT_TYPE = "application/vnd.sqlite3"
_PNG_CONTENT_TYPE = "image/png"
_IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
_THUMBNAIL_CONTENT_TYPE = "image/webp"
_MAX_POOL_CONNECTIONS = 16
_LOGGER = logging.getLogger(__name__)


def _error_code(error: ClientError) -> str | None:
    """Read one S3 error code without assuming a particular provider."""

    code = error.response.get("Error", {}).get("Code")
    return code if isinstance(code, str) else None


def _is_missing(error: ClientError) -> bool:
    """Return whether a provider reported an absent object."""

    return _error_code(error) in {"404", "NoSuchKey", "NotFound"}


class ObjectStore(Protocol):
    """Pull and push the database and its archive assets."""

    async def pull_database(self, destination: Path) -> bool:
        """Download the current database, returning false when it does not exist."""
        ...

    async def push_database(self, source: Path) -> None:
        """Replace the current database with the completed local file."""
        ...

    async def put_png(self, key: str, artifact: PngImage) -> None:
        """Create one immutable archive-asset PNG object."""
        ...

    async def put_thumbnail(self, key: str, content: bytes) -> None:
        """Replace one derived WebP thumbnail object."""
        ...

    async def put_video(self, key: str, artifact: FileVideoArtifact) -> None:
        """Create one immutable video object."""
        ...

    async def put_audio(self, key: str, artifact: FileAudioArtifact) -> None:
        """Create one immutable story audio object."""
        ...


class S3ObjectStore:
    """Store the database and archive assets in one versioned S3-compatible bucket.

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
        database_cache_dir: Path | None = None,
    ) -> None:
        """Configure access to one S3-compatible bucket."""
        self._bucket = bucket
        self._database_cache = UpstreamCache(database_cache_dir) if database_cache_dir else None
        self.database_cache_key: str | None = None
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
        if self._database_cache is not None:
            return await self._pull_cached_database(destination)
        return await await_owned(asyncio.to_thread(self._pull_database, destination))

    async def _pull_cached_database(self, destination: Path) -> bool:
        """Check the origin ETag, then copy a verified, unchanged generation for this check."""
        self.database_cache_key = None
        try:
            metadata = await await_owned(
                asyncio.to_thread(
                    self._client.head_object, Bucket=self._bucket, Key=DATABASE_OBJECT_KEY
                )
            )
        except ClientError as error:
            if not _is_missing(error):
                raise
            destination.unlink(missing_ok=True)
            return False
        etag, size = metadata.get("ETag"), metadata.get("ContentLength")
        if not isinstance(etag, str) or not etag or type(size) is not int or size <= 0:
            raise ValueError("Invalid published database metadata")
        fingerprint = hashlib.sha256(
            json.dumps([self._client.meta.endpoint_url, self._bucket, etag, size]).encode()
        ).hexdigest()
        destination.parent.mkdir(parents=True, exist_ok=True)

        def download(directory: Path) -> None:
            """Download the observed generation, refusing a concurrent replacement."""
            response = self._client.get_object(
                Bucket=self._bucket, Key=DATABASE_OBJECT_KEY, IfMatch=etag
            )
            with closing(response["Body"]) as body:
                if response.get("ETag") != etag or response.get("ContentLength") != size:
                    raise ValueError("Published database changed during download")
                path = directory / DATABASE_OBJECT_KEY
                with path.open("wb") as stream:
                    shutil.copyfileobj(body, stream, length=1024 * 1024)
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            (directory / "metadata.json").write_text(
                json.dumps({"sha256": digest, "cache_key": f"{fingerprint}-{uuid.uuid4().hex}"}),
                encoding="utf-8",
            )
            _LOGGER.info("preflight database cache status=downloaded bytes=%s", size)

        async def produce(directory: Path) -> None:
            """Keep the streaming download off the event loop."""
            await await_owned(asyncio.to_thread(download, directory))

        def validate(directory: Path) -> str:
            """Verify cached bytes and copy them under the cache lock before validation."""
            path = directory / DATABASE_OBJECT_KEY
            cached = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            key = cached["cache_key"]
            if not isinstance(key, str) or not re.fullmatch(f"{fingerprint}-[0-9a-f]{{32}}", key):
                raise ValueError("Invalid database cache key")
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if path.stat().st_size != size or digest != cached["sha256"]:
                raise ValueError("Invalid database cache content")
            shutil.copyfile(path, destination)
            return key

        cached = await self._database_cache.directory(
            "published",
            Path("database"),
            fingerprint,
            produce,
            validate,
            on_hit=lambda: _LOGGER.info("preflight database cache status=cached bytes=%s", size),
        )
        self.database_cache_key = cached.value
        return True

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
            "CacheControl": _IMMUTABLE_CACHE_CONTROL,
        }
        if artifact.path is None:
            self._client.put_object(Body=artifact.content, **request)
        else:
            with artifact.path.open("rb") as content:
                self._client.put_object(Body=content, **request)

    async def put_video(self, key: str, artifact: FileVideoArtifact) -> None:
        """Create one video, accepting an already matching immutable object."""

        await await_owned(asyncio.to_thread(self._put_video, key, artifact))

    def _put_video(self, key: str, artifact: FileVideoArtifact) -> None:
        try:
            existing = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if not _is_missing(error):
                raise
        else:
            self._validate_video(key, artifact, existing)
            return

        with artifact.path.open("rb") as content:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentLength=artifact.byte_size,
                ContentType=artifact.content_type,
                CacheControl=_IMMUTABLE_CACHE_CONTROL,
            )

    async def put_audio(self, key: str, artifact: FileAudioArtifact) -> None:
        """Create one audio object, accepting an already matching immutable object."""

        await await_owned(asyncio.to_thread(self._put_audio, key, artifact))

    def _put_audio(self, key: str, artifact: FileAudioArtifact) -> None:
        try:
            existing = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if not _is_missing(error):
                raise
        else:
            self._validate_audio(key, artifact, existing)
            return

        with artifact.path.open("rb") as content:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentLength=artifact.byte_size,
                ContentType=artifact.content_type,
                CacheControl=_IMMUTABLE_CACHE_CONTROL,
            )

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
            "CacheControl": _IMMUTABLE_CACHE_CONTROL,
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

    @staticmethod
    def _validate_video(
        key: str,
        artifact: FileVideoArtifact,
        metadata: dict[str, object],
    ) -> None:
        """Require an existing object to match the immutable video contract."""

        expected = {
            "ContentLength": artifact.byte_size,
            "ContentType": artifact.content_type,
            "CacheControl": _IMMUTABLE_CACHE_CONTROL,
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
            raise ValueError(f"immutable video object conflicts with {key}: {detail}")

    @staticmethod
    def _validate_audio(
        key: str,
        artifact: FileAudioArtifact,
        metadata: dict[str, object],
    ) -> None:
        """Require an existing object to match the immutable audio contract."""

        expected = {
            "ContentLength": artifact.byte_size,
            "ContentType": artifact.content_type,
            "CacheControl": _IMMUTABLE_CACHE_CONTROL,
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
            raise ValueError(f"immutable audio object conflicts with {key}: {detail}")


class MemoryObjectStore:
    """Store database and archive-asset bytes in memory for deterministic tests."""

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

    async def put_video(self, key: str, artifact: FileVideoArtifact) -> None:
        """Create one immutable video or accept an identical existing value."""

        content = artifact.content
        existing = self.objects.setdefault(key, content)
        if existing != content:
            raise ValueError(f"immutable video object conflicts with {key}")

    async def put_audio(self, key: str, artifact: FileAudioArtifact) -> None:
        """Create one immutable audio object or accept an identical value."""

        content = artifact.content
        existing = self.objects.setdefault(key, content)
        if existing != content:
            raise ValueError(f"immutable audio object conflicts with {key}")
