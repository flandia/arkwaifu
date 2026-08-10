"""Coordinate remote preparation and atomic publication of Arkwaifu data.

The operation has three parts, following the previous Go update loop: pull and
prepare the upstream data, convert it into the database and PNG forms consumed
by the reader, and submit the resulting objects. Preparation may use cached
intermediate files, but one database overwrite is the final visibility point.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from .asyncio_tools import await_owned
from .database import (
    apply_changes,
    find_missing_art_references,
    initialize_or_validate,
    read_versions,
)
from .domain import ArtManifest, LocaleManifest, PngImage
from .object_store import ObjectStore

UpdateUnit = Literal["art", "CN", "EN", "JP", "KR", "TW"]
Manifest = ArtManifest | LocaleManifest
BuildManifest = Callable[[str | None, bool], Awaitable[Manifest]]
UpdateStatus = Literal["updated", "unchanged"]

_UNITS = frozenset({"art", "CN", "EN", "JP", "KR", "TW"})
_INCOMPLETE_UPSTREAM_LOGGER = logging.getLogger("arkwaifu_updateloop.incomplete_upstream")


@dataclass(frozen=True, slots=True)
class Update:
    """Describe one requested dataset and the callback which prepares it."""

    unit: UpdateUnit
    res_version: str
    build: BuildManifest


@dataclass(frozen=True, slots=True)
class UpdateResult:
    """Report whether one requested dataset changed the published database."""

    unit: UpdateUnit
    res_version: str
    status: UpdateStatus


def _prepare_art_publication(
    manifests: Sequence[Manifest],
) -> tuple[dict[str, str], dict[str, str], tuple[tuple[str, PngImage], ...]]:
    """Derive object keys and candidate uploads from the requested art manifest."""

    manifest = next(
        (manifest for manifest in manifests if isinstance(manifest, ArtManifest)),
        None,
    )
    if manifest is None:
        return {}, {}, ()
    art_keys = {
        art.id: art_object_key(
            res_version=manifest.upstream_version,
            variant="composition",
            category=art.category,
            identifier=art.id,
        )
        for art in manifest.arts
    }
    source_keys = {
        source.id: art_object_key(
            res_version=manifest.upstream_version,
            variant="source",
            category="character",
            identifier=source.id,
        )
        for source in manifest.source_arts
    }
    uploads = tuple(
        [(art_keys[art.id], art.image) for art in manifest.arts]
        + [(source_keys[source.id], source.image) for source in manifest.source_arts]
    )
    return art_keys, source_keys, uploads


def art_object_key(
    *,
    res_version: str,
    variant: str,
    category: str,
    identifier: str,
) -> str:
    """Return the escaped object key for one art composition or source image."""

    if variant not in {"composition", "source"}:
        raise ValueError(f"unknown art object variant: {variant}")
    if category not in {"image", "background", "item", "character"}:
        raise ValueError(f"unknown art object category: {category}")
    segments = ("ART", res_version, variant, category, f"{identifier}.png")
    return "/".join(quote(segment, safe="") for segment in segments)


class Updateloop:
    """Keep the remote Arkwaifu database and its PNG objects up-to-date."""

    def __init__(self, remote: ObjectStore, *, upload_workers: int = 16) -> None:
        if upload_workers <= 0:
            raise ValueError("upload workers must be positive")
        self._remote = remote
        self._upload_workers = upload_workers

    async def run(
        self,
        requests: Sequence[Update],
        *,
        force: bool = False,
    ) -> tuple[UpdateResult, ...]:
        """Prepare and publish all requested changes as one operation.

        Builders run concurrently. Successful manifests enter one local SQLite
        transaction, final PNG winners upload with bounded concurrency, and the
        database uploads last. A failure before the final upload leaves the
        previously published database current, although completed PNG uploads
        can remain unreferenced.
        """

        self._validate_requests(requests)
        if not requests:
            return ()

        with tempfile.TemporaryDirectory(prefix="arkwaifu-database-") as temporary:
            database_path = Path(temporary) / "arkwaifu.sqlite3"
            await await_owned(self._remote.pull_database(database_path))
            await await_owned(asyncio.to_thread(initialize_or_validate, database_path))
            active_versions = await await_owned(asyncio.to_thread(read_versions, database_path))

            if force and any(
                request.unit == "art" and active_versions.get("art") == request.res_version
                for request in requests
            ):
                raise ValueError(
                    "cannot force art at the published resVersion: stable PNG keys "
                    "would change before the database publication point"
                )

            changed_requests = [
                request
                for request in requests
                if force or active_versions.get(request.unit) != request.res_version
            ]
            if not changed_requests:
                return tuple(
                    UpdateResult(request.unit, request.res_version, "unchanged")
                    for request in requests
                )
            manifests = await self._build_manifests(changed_requests, active_versions, force)
            art_keys, source_keys, candidate_uploads = _prepare_art_publication(manifests)
            committed_object_keys = await await_owned(
                asyncio.to_thread(
                    apply_changes,
                    database_path,
                    manifests,
                    art_keys=art_keys,
                    source_keys=source_keys,
                )
            )
            referenced_uploads = tuple(
                (key, artifact)
                for key, artifact in candidate_uploads
                if key in committed_object_keys
            )
            missing = await await_owned(
                asyncio.to_thread(find_missing_art_references, database_path)
            )
            if missing:
                _INCOMPLETE_UPSTREAM_LOGGER.warning(
                    "database references unavailable art; continuing count=%d sample=%s",
                    len(missing),
                    list(missing[:10]),
                )
            await self._upload_artifacts(referenced_uploads)
            await await_owned(self._remote.push_database(database_path))

            changed_units = {request.unit for request in changed_requests}
            return tuple(
                UpdateResult(
                    request.unit,
                    request.res_version,
                    "updated" if request.unit in changed_units else "unchanged",
                )
                for request in requests
            )

    @staticmethod
    def _validate_requests(requests: Sequence[Update]) -> None:
        seen: set[str] = set()
        for request in requests:
            if request.unit not in _UNITS:
                raise ValueError(f"unknown database unit: {request.unit}")
            if not request.res_version:
                raise ValueError(f"{request.unit} resVersion cannot be empty")
            if request.unit in seen:
                raise ValueError(f"database unit requested more than once: {request.unit}")
            seen.add(request.unit)

    @staticmethod
    async def _build_manifests(
        requests: Sequence[Update],
        active_versions: dict[str, str],
        force: bool,
    ) -> tuple[Manifest, ...]:
        async def build(request: Update) -> Manifest:
            manifest = await request.build(active_versions.get(request.unit), force)
            if request.unit == "art":
                if not isinstance(manifest, ArtManifest):
                    raise TypeError("art builder returned a locale manifest")
            elif not isinstance(manifest, LocaleManifest) or manifest.unit != request.unit:
                raise TypeError(f"{request.unit} builder returned a different locale manifest")
            if manifest.upstream_version != request.res_version:
                raise ValueError(
                    f"{request.unit} builder returned resVersion "
                    f"{manifest.upstream_version!r}, expected {request.res_version!r}"
                )
            if isinstance(manifest, LocaleManifest):
                missing_sections = [
                    name
                    for name, records in (
                        ("story_groups", manifest.story_groups),
                        ("galleries", manifest.galleries),
                    )
                    if not records
                ]
                if missing_sections:
                    _INCOMPLETE_UPSTREAM_LOGGER.warning(
                        "prepared locale data is incomplete; continuing "
                        "unit=%s res_version=%s missing=%s",
                        manifest.unit,
                        manifest.upstream_version,
                        ",".join(missing_sections),
                    )
            return manifest

        tasks = [
            asyncio.create_task(build(request), name=f"build-{request.unit}")
            for request in requests
        ]
        try:
            return tuple(await asyncio.gather(*tasks))
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def _upload_artifacts(
        self,
        uploads: Sequence[tuple[str, PngImage]],
    ) -> None:
        """Upload final manifest winners with bounded memory and concurrency."""
        if not uploads:
            return
        iterator = iter(uploads)
        stop = asyncio.Event()
        first_error: Exception | None = None

        async def worker() -> None:
            nonlocal first_error
            while not stop.is_set():
                try:
                    key, artifact = next(iterator)
                except StopIteration:
                    return
                try:
                    await self._remote.put_png(key, artifact)
                except Exception as error:  # noqa: BLE001 - adapter errors are opaque
                    if first_error is None:
                        first_error = error
                    stop.set()
                    return

        tasks = [
            asyncio.create_task(worker(), name=f"batch-art-upload-{index}")
            for index in range(min(self._upload_workers, len(uploads)))
        ]
        batch = asyncio.gather(*tasks)
        try:
            await asyncio.shield(batch)
        except asyncio.CancelledError:
            stop.set()
            await await_owned(batch)
            raise
        if first_error is not None:
            raise first_error
