"""Store immutable upstream asset-bundle wrappers and version manifests."""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .asyncio_tools import await_owned

_BUNDLE_CONTENT_TYPE = "application/octet-stream"
_MANIFEST_CONTENT_TYPE = "application/json"
_IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
_MANIFEST_NAME = "hot_update_list.json"
_MANIFEST_DIGEST = re.compile(r"(?:[0-9a-f]{4}|[0-9a-f]{32})")
_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}")
_SAFE_FILENAME = re.compile(r"[^\x00-\x1f\x7f/\\]{1,256}")


def _error_code(error: ClientError) -> str | None:
    code = error.response.get("Error", {}).get("Code")
    return code if isinstance(code, str) else None


def _is_missing(error: ClientError) -> bool:
    return _error_code(error) in {"404", "NoSuchKey", "NotFound"}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_segment(value: str, context: str) -> str:
    if not _SAFE_SEGMENT.fullmatch(value):
        raise ValueError(f"unsafe {context}: {value!r}")
    return value


def _safe_filename(value: str) -> str:
    if not _SAFE_FILENAME.fullmatch(value):
        raise ValueError(f"unsafe archive filename: {value!r}")
    return value


class AssetBundleArchiveStore(Protocol):
    """Persist one ordered CN/Windows asset-bundle archive."""

    async def completed_versions(self) -> frozenset[str]:
        """Return versions whose final manifest object exists."""
        ...

    async def read_manifest(self, version: str) -> bytes:
        """Read one completed version's exact upstream manifest."""
        ...

    async def put_bundle(
        self,
        version: str,
        filename: str,
        source: Path,
        *,
        bundle_md5: str,
    ) -> bool:
        """Create one immutable CDN wrapper, returning whether it was uploaded."""
        ...

    async def put_manifest(self, version: str, source: Path) -> bool:
        """Create the immutable completion manifest after every wrapper."""
        ...


class S3AssetBundleArchiveStore:
    """Archive asset-bundle wrappers in an S3-compatible bucket."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str,
        path_style: bool = False,
        game_region: str = "CN",
        architecture: str = "Windows",
        max_pool_connections: int = 16,
    ) -> None:
        """Configure the archive prefix and its S3 adapter."""

        if max_pool_connections <= 0:
            raise ValueError("max_pool_connections must be positive")
        self._bucket = bucket
        self._prefix = "/".join(
            (
                _safe_segment(game_region, "game region"),
                _safe_segment(architecture, "architecture"),
            )
        )
        self._client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
            config=Config(
                max_pool_connections=max_pool_connections,
                s3={"addressing_style": "path" if path_style else "virtual"},
            ),
        )

    async def completed_versions(self) -> frozenset[str]:
        """List final manifests below the configured region and architecture."""

        return await await_owned(asyncio.to_thread(self._completed_versions))

    def _completed_versions(self) -> frozenset[str]:
        prefix = f"{self._prefix}/"
        version_prefixes: set[str] = set()
        continuation: str | None = None
        while True:
            request = {"Bucket": self._bucket, "Prefix": prefix, "Delimiter": "/"}
            if continuation is not None:
                request["ContinuationToken"] = continuation
            response = self._client.list_objects_v2(**request)
            for item in response.get("CommonPrefixes", ()):
                candidate = item.get("Prefix") if isinstance(item, dict) else None
                if not isinstance(candidate, str) or not candidate.startswith(prefix):
                    continue
                version = candidate.removeprefix(prefix).removesuffix("/")
                _safe_segment(version, "archive version")
                if candidate == f"{prefix}{version}/":
                    version_prefixes.add(candidate)
            if not response.get("IsTruncated"):
                break
            continuation = response.get("NextContinuationToken")
            if not isinstance(continuation, str) or not continuation:
                raise ValueError("truncated archive listing has no continuation token")

        versions: set[str] = set()
        for version_prefix in version_prefixes:
            version = version_prefix.removeprefix(prefix).removesuffix("/")
            try:
                self._client.head_object(
                    Bucket=self._bucket,
                    Key=f"{version_prefix}{_MANIFEST_NAME}",
                )
            except ClientError as error:
                if not _is_missing(error):
                    raise
            else:
                versions.add(version)
        return frozenset(versions)

    async def read_manifest(self, version: str) -> bytes:
        """Download one archived completion manifest."""

        return await await_owned(asyncio.to_thread(self._read_manifest, version))

    def _read_manifest(self, version: str) -> bytes:
        response = self._client.get_object(
            Bucket=self._bucket,
            Key=self._key(version, _MANIFEST_NAME),
        )
        body = response.get("Body")
        if body is None or not hasattr(body, "read"):
            raise TypeError(f"archive manifest has no readable body: {version}")
        content = body.read()
        if not isinstance(content, bytes):
            raise TypeError(f"archive manifest body is not bytes: {version}")
        return content

    async def put_bundle(
        self,
        version: str,
        filename: str,
        source: Path,
        *,
        bundle_md5: str,
    ) -> bool:
        """Create or validate one immutable CDN wrapper."""

        return await await_owned(
            asyncio.to_thread(
                self._put_file,
                self._key(version, filename),
                source,
                _BUNDLE_CONTENT_TYPE,
                {"manifest-md5": self._manifest_digest(bundle_md5)},
            )
        )

    async def put_manifest(self, version: str, source: Path) -> bool:
        """Create or validate one immutable completion manifest."""

        return await await_owned(
            asyncio.to_thread(
                self._put_file,
                self._key(version, _MANIFEST_NAME),
                source,
                _MANIFEST_CONTENT_TYPE,
                {},
            )
        )

    def _put_file(
        self,
        key: str,
        source: Path,
        content_type: str,
        metadata: dict[str, str],
    ) -> bool:
        byte_size = source.stat().st_size
        expected_metadata = {**metadata, "sha256": _digest(source)}
        try:
            existing = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if not _is_missing(error):
                raise
        else:
            self._validate_existing(
                key,
                existing,
                byte_size=byte_size,
                content_type=content_type,
                metadata=expected_metadata,
            )
            return False

        with source.open("rb") as content:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentLength=byte_size,
                ContentType=content_type,
                CacheControl=_IMMUTABLE_CACHE_CONTROL,
                Metadata=expected_metadata,
            )
        return True

    @staticmethod
    def _validate_existing(
        key: str,
        existing: dict[str, object],
        *,
        byte_size: int,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        actual_metadata = existing.get("Metadata")
        expected: dict[str, object] = {
            "ContentLength": byte_size,
            "ContentType": content_type,
            "CacheControl": _IMMUTABLE_CACHE_CONTROL,
            "Metadata": metadata,
        }
        actual: dict[str, object] = {
            "ContentLength": existing.get("ContentLength"),
            "ContentType": existing.get("ContentType"),
            "CacheControl": existing.get("CacheControl"),
            "Metadata": actual_metadata if isinstance(actual_metadata, dict) else {},
        }
        mismatches = {
            field: (actual[field], wanted)
            for field, wanted in expected.items()
            if actual[field] != wanted
        }
        if mismatches:
            detail = ", ".join(
                f"{field}={found!r} (expected {wanted!r})"
                for field, (found, wanted) in mismatches.items()
            )
            raise ValueError(
                f"immutable asset-bundle archive object conflicts with {key}: {detail}"
            )

    def _key(self, version: str, filename: str) -> str:
        return "/".join(
            (
                self._prefix,
                _safe_segment(version, "archive version"),
                _safe_filename(filename),
            )
        )

    @staticmethod
    def _manifest_digest(value: str) -> str:
        normalized = value.lower()
        if not _MANIFEST_DIGEST.fullmatch(normalized):
            raise ValueError(f"invalid asset-bundle manifest digest: {value!r}")
        return normalized


class MemoryAssetBundleArchiveStore:
    """Keep a deterministic asset-bundle archive for interface tests."""

    def __init__(self) -> None:
        """Create an empty archive."""

        self.objects: dict[str, bytes] = {}
        self.bundle_md5: dict[str, str] = {}

    async def completed_versions(self) -> frozenset[str]:
        """Return versions with a final manifest."""

        suffix = f"/{_MANIFEST_NAME}"
        return frozenset(key.removesuffix(suffix) for key in self.objects if key.endswith(suffix))

    async def read_manifest(self, version: str) -> bytes:
        """Read a completed in-memory manifest."""

        return self.objects[f"{version}/{_MANIFEST_NAME}"]

    async def put_bundle(
        self,
        version: str,
        filename: str,
        source: Path,
        *,
        bundle_md5: str,
    ) -> bool:
        """Create or validate one immutable in-memory wrapper."""

        key = f"{version}/{filename}"
        content = source.read_bytes()
        created = key not in self.objects
        existing = self.objects.setdefault(key, content)
        existing_md5 = self.bundle_md5.setdefault(key, bundle_md5)
        if existing != content or existing_md5 != bundle_md5:
            raise ValueError(f"immutable asset-bundle archive object conflicts with {key}")
        return created

    async def put_manifest(self, version: str, source: Path) -> bool:
        """Create or validate one immutable in-memory completion manifest."""

        key = f"{version}/{_MANIFEST_NAME}"
        content = source.read_bytes()
        created = key not in self.objects
        existing = self.objects.setdefault(key, content)
        if existing != content:
            raise ValueError(f"immutable asset-bundle archive object conflicts with {key}")
        return created
