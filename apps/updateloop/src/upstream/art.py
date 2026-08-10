"""Pull and process art from the Arknights asset API.

An art resource passes through four cacheable stages:

``fetched``
    Download the CDN wrapper and verify its embedded bundle against the MD5
    published in ``hot_update_list.json``.
``unwrapped``
    Extract the Unity bundle from the wrapper ZIP.
``extracted``
    Export the Unity objects into the normalized asset tree.
``rendered``
    Merge alpha channels and character variations into PNG manifests.

Resources run concurrently. Downloads are bounded separately from the process
pool used by extraction and rendering.
"""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import io
import json
import logging
import os
import re
import zipfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx

from ..art import (
    build_art_manifest,
    merge_art_manifests,
    read_art_manifest,
    write_art_manifest,
)
from ..asyncio_tools import await_owned
from ..domain import ArtManifest
from ..extraction import extract_assets
from .cache import UpstreamCache

_ART_PATTERNS = (
    "avg/imgs/**",
    "avg/images/**",
    "avg/bg/**",
    "avg/items/**",
    "avg/characters/**",
)
# Bump a stage when its persisted layout or recipe changes. Each fingerprint
# includes earlier formats, so changing one stage also invalidates its dependents.
_ART_STAGE_FORMATS = {
    "fetched": "1",
    "unwrapped": "1",
    "extracted": "1",
    "rendered": "1",
}
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _Resource:
    """Identify one asset bundle by its upstream name and integrity checksum."""

    name: str
    md5: str


def _bundle_md5(wrapper: bytes, resource_name: str) -> str:
    """Calculate the upstream checksum of one bundle inside its CDN wrapper."""

    with zipfile.ZipFile(io.BytesIO(wrapper)) as archive:
        return _archive_member_md5(archive, resource_name)


def _archive_member_md5(archive: zipfile.ZipFile, resource_name: str) -> str:
    """Calculate an archive member's MD5 without loading the bundle in memory."""

    try:
        member = archive.getinfo(resource_name)
    except KeyError as error:
        raise ValueError(f"download does not contain {resource_name}") from error
    digest = hashlib.md5(usedforsecurity=False)
    with archive.open(member) as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _unzip_resource(wrapper: Path, resource_name: str, destination: Path) -> None:
    """Unwrap one named Unity bundle without trusting archive paths."""

    relative = _resource_member_path(resource_name)
    output = destination.joinpath(*relative.parts).resolve()
    output.relative_to(destination.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wrapper) as archive:
        try:
            member = archive.getinfo(resource_name)
        except KeyError as error:
            raise ValueError(f"download does not contain {resource_name}") from error
        with archive.open(member) as source, output.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)


def _render_art_resource(
    extracted: Path,
    rendered: Path,
    upstream_version: str,
) -> None:
    """Process one extracted resource and write its file-backed manifest."""

    manifest = build_art_manifest(extracted, upstream_version)
    write_art_manifest(manifest, rendered)


def _extract_and_render_art_resource(
    bundle: Path,
    extracted: Path,
    rendered: Path,
    upstream_version: str,
) -> None:
    """Populate both expensive stages in one disposable child on a cold miss."""
    extract_assets([bundle], extracted, workers=1)
    _render_art_resource(extracted, rendered, upstream_version)


def _resource_member_path(resource_name: str) -> PurePosixPath:
    """Parse an upstream bundle name that is safe to place below a directory."""

    parts = resource_name.split("/")
    if not resource_name or "\\" in resource_name or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe upstream resource name: {resource_name!r}")
    relative = PurePosixPath(*parts)
    if relative.is_absolute():
        raise ValueError(f"unsafe upstream resource name: {resource_name!r}")
    return relative


def _resource_cache_path(resource: _Resource) -> PurePosixPath:
    """Identify a resource with its readable name and upstream-provided MD5."""
    _resource_member_path(resource.name)
    content_identity = quote(resource.md5, safe="") or "unknown-md5"
    return PurePosixPath(
        "art",
        "resources",
        quote(resource.name, safe=""),
        content_identity,
    )


def _stage_fingerprint(stage: str, resource: _Resource) -> str:
    """Describe every input format on which a cached stage depends.

    Changing an early format invalidates that stage and every stage after it,
    while leaving independent resources and earlier compatible work reusable.
    """

    stage_order = tuple(_ART_STAGE_FORMATS)
    dependency_formats = {
        name: _ART_STAGE_FORMATS[name] for name in stage_order[: stage_order.index(stage) + 1]
    }
    return json.dumps(
        {
            "formats": dependency_formats,
            "resource": resource.name,
            "md5": resource.md5,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


class LiveArtBuilder:
    """Fetch and build an art delta for one detected upstream version.

    Unless forced, only bundles whose name or published MD5 changed since the
    published version are processed. The existing database retains unchanged art.
    """

    def __init__(
        self,
        *,
        version_url: str,
        asset_base_url: str,
        cache: UpstreamCache,
        download_workers: int = 16,
        extraction_workers: int | None = None,
    ) -> None:
        if download_workers <= 0:
            raise ValueError("download_workers must be positive")
        if extraction_workers is not None and extraction_workers <= 0:
            raise ValueError("extraction_workers must be positive")
        if os.name == "nt" and extraction_workers is not None and extraction_workers > 61:
            raise ValueError("extraction_workers cannot exceed 61 on Windows")
        self._version_url = version_url
        self._asset_base_url = asset_base_url.rstrip("/")
        self._download_workers = download_workers
        self._extraction_workers = extraction_workers
        self._cache = cache

    async def detect_version(self) -> str:
        """Get the current ``resVersion`` from the configured version API."""

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(self._version_url)
            response.raise_for_status()
            version = response.json().get("resVersion")
        if not isinstance(version, str) or not version:
            raise ValueError("upstream version response does not contain resVersion")
        return version

    async def build(
        self,
        upstream_version: str,
        active_version: str | None,
        force: bool,
    ) -> ArtManifest:
        """Fetch, extract, and render the art resources that need updating."""

        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            if active_version and not force:
                current, previous = await asyncio.gather(
                    self._resources(client, upstream_version),
                    self._resources(client, active_version),
                )
                previous_keys = {(resource.name, resource.md5) for resource in previous}
                selected = [
                    resource
                    for resource in current
                    if (resource.name, resource.md5) not in previous_keys
                ]
            else:
                current = await self._resources(client, upstream_version)
                selected = current
            manifests = (
                await self._process_resources(client, upstream_version, selected)
                if selected
                else []
            )
        return merge_art_manifests(manifests, upstream_version)

    async def _resources(self, client: httpx.AsyncClient, version: str) -> list[_Resource]:
        """Get the cached hot-update list for one resource version."""

        url = f"{self._asset_base_url}/{quote(version, safe='')}/hot_update_list.json"

        async def fetch(destination: Path) -> None:
            response = await client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)

        path = await self._cache.file(
            version,
            PurePosixPath("art", "hot_update_list.json"),
            fetch,
            self._validate_resource_list,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self._parse_resources(payload, version)

    @staticmethod
    def _parse_resources(payload: object, version: str) -> list[_Resource]:
        """Select art bundles from a HyperGryph hot-update list."""

        raw = payload.get("abInfos") if isinstance(payload, dict) else None
        if not isinstance(raw, list):
            raise TypeError(f"resource list for {version} does not contain abInfos")
        resources = [
            _Resource(name=str(item["name"]), md5=str(item["md5"]).lower())
            for item in raw
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and any(fnmatch.fnmatchcase(item["name"], pattern) for pattern in _ART_PATTERNS)
        ]
        return sorted(resources, key=lambda resource: resource.name)

    @classmethod
    def _validate_resource_list(cls, path: Path) -> None:
        cls._parse_resources(json.loads(path.read_text(encoding="utf-8")), path.parent.name)

    def _resource_url(self, version: str, resource: _Resource) -> str:
        """Translate a logical bundle name to its CDN wrapper URL."""

        filename = resource.name.replace("/", "_").replace("#", "__")
        filename = re.sub(r"\.(.*?)$", ".dat", filename)
        return f"{self._asset_base_url}/{quote(version, safe='')}/{quote(filename, safe='')}"

    async def _process_resources(
        self,
        client: httpx.AsyncClient,
        version: str,
        resources: list[_Resource],
    ) -> list[ArtManifest]:
        """Run the cache stages concurrently for every selected resource."""

        semaphore = asyncio.Semaphore(self._download_workers)
        loop = asyncio.get_running_loop()
        executor = ProcessPoolExecutor(
            max_workers=self._extraction_workers,
            max_tasks_per_child=1,
        )

        async def process(resource: _Resource) -> ArtManifest:
            resource_root = _resource_cache_path(resource)

            def validate_rendered(destination: Path) -> ArtManifest:
                manifest = read_art_manifest(destination)
                if manifest.upstream_version != version:
                    raise ValueError(
                        "rendered art resource has the wrong upstream version: "
                        f"{manifest.upstream_version!r}, expected {version!r}"
                    )
                return manifest

            async def materialize_rendered(rendered: Path) -> None:
                rendered_by_extractor = False

                async def materialize_extracted(extracted: Path) -> None:
                    nonlocal rendered_by_extractor

                    async def materialize_unwrapped(unwrapped: Path) -> None:
                        async def materialize_fetched(fetched: Path) -> None:
                            async with semaphore:
                                await self._download_resource(
                                    client,
                                    version,
                                    resource,
                                    fetched / "wrapper.dat",
                                )

                        fetched = await self._cache.directory(
                            version,
                            resource_root / "fetched",
                            _stage_fingerprint("fetched", resource),
                            materialize_fetched,
                            lambda path: self._validate_fetched(path, resource),
                        )
                        await await_owned(
                            asyncio.to_thread(
                                _unzip_resource,
                                fetched.path / "wrapper.dat",
                                resource.name,
                                unwrapped,
                            )
                        )

                    unwrapped = await self._cache.directory(
                        version,
                        resource_root / "unwrapped",
                        _stage_fingerprint("unwrapped", resource),
                        materialize_unwrapped,
                        lambda path: self._validate_unwrapped(path, resource),
                    )
                    bundle = unwrapped.path.joinpath(*_resource_member_path(resource.name).parts)
                    await await_owned(
                        loop.run_in_executor(
                            executor,
                            _extract_and_render_art_resource,
                            bundle,
                            extracted,
                            rendered,
                            version,
                        )
                    )
                    rendered_by_extractor = True

                extracted = await self._cache.directory(
                    version,
                    resource_root / "extracted",
                    _stage_fingerprint("extracted", resource),
                    materialize_extracted,
                    self._validate_extracted,
                )
                if not rendered_by_extractor:
                    await await_owned(
                        loop.run_in_executor(
                            executor,
                            _render_art_resource,
                            extracted.path,
                            rendered,
                            version,
                        )
                    )

            rendered = await self._cache.directory(
                version,
                resource_root / "rendered",
                _stage_fingerprint("rendered", resource),
                materialize_rendered,
                validate_rendered,
            )
            if not isinstance(rendered.value, ArtManifest):
                raise TypeError(f"rendered art resource has no manifest: {rendered.path}")
            return rendered.value

        tasks = [asyncio.create_task(process(resource)) for resource in resources]
        try:
            manifests = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        finally:
            await await_owned(asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True))

        _LOGGER.info(
            "art pipeline completed resources=%s download_workers=%s extraction_workers=%s",
            len(resources),
            self._download_workers,
            self._extraction_workers or "default",
        )
        return list(manifests)

    async def _download_resource(
        self,
        client: httpx.AsyncClient,
        version: str,
        resource: _Resource,
        destination: Path,
    ) -> None:
        """Download one wrapper, retrying until it passes upstream admission."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        await self._fetch_bundle(client, version, resource, destination)

    async def _fetch_bundle(
        self,
        client: httpx.AsyncClient,
        version: str,
        resource: _Resource,
        destination: Path,
        *,
        validate: bool = True,
    ) -> None:
        """Stream one CDN wrapper to disk and retry one failed attempt."""

        url = self._resource_url(version, resource)
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with destination.open("wb") as output:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            output.write(chunk)
                if validate:
                    await await_owned(
                        asyncio.to_thread(self._validate_bundle, destination, resource)
                    )
                return
            except (httpx.HTTPError, OSError, ValueError, zipfile.BadZipFile) as error:
                last_error = error
                destination.unlink(missing_ok=True)
                if attempt == 0:
                    await asyncio.sleep(0.25)
        raise RuntimeError(f"failed to download {resource.name}") from last_error

    @staticmethod
    def _validate_bundle(path: Path, resource: _Resource) -> None:
        """Verify the wrapper and its bundle against upstream's MD5."""

        with zipfile.ZipFile(path) as archive:
            digest = _archive_member_md5(archive, resource.name)
        if resource.md5 and digest != resource.md5:
            raise ValueError(
                f"MD5 mismatch for {resource.name}: expected {resource.md5}, got {digest}"
            )

    @staticmethod
    def _validate_fetched(path: Path, resource: _Resource) -> Path:
        """Validate a completed ``fetched`` cache stage."""

        wrapper = path / "wrapper.dat"
        LiveArtBuilder._validate_bundle(wrapper, resource)
        return wrapper

    @staticmethod
    def _validate_unwrapped(path: Path, resource: _Resource) -> Path:
        """Validate an unwrapped bundle against the same upstream MD5."""

        bundle = path.joinpath(*_resource_member_path(resource.name).parts)
        if not bundle.is_file():
            raise ValueError(f"unwrapped bundle is missing: {bundle}")
        if resource.md5:
            digest = hashlib.md5(usedforsecurity=False)
            with bundle.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
            actual = digest.hexdigest()
            if actual != resource.md5:
                raise ValueError(
                    f"MD5 mismatch for {resource.name}: expected {resource.md5}, got {actual}"
                )
        return bundle

    @staticmethod
    def _validate_extracted(path: Path) -> Path:
        """Reject incomplete or unsafe extracted trees before cache reuse."""

        if not path.is_dir():
            raise ValueError(f"extracted art tree is missing: {path}")
        for candidate in path.rglob("*"):
            if candidate.is_symlink():
                raise ValueError(f"extracted art tree contains a symlink: {candidate}")
        return path
