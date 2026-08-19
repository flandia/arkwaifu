"""Coordinate remote preparation and publication of Arkwaifu data.

The operation has three parts, following the previous Go update loop: pull and
prepare the upstream data, convert it into the database and image forms consumed
by the reader, and submit the resulting objects. Preparation may use cached
intermediate files, but one database overwrite is the metadata visibility point.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from .asyncio_tools import await_owned
from .database import (
    apply_changes,
    find_missing_artwork_references,
    find_missing_media_references,
    find_missing_score_references,
    initialize_or_validate,
    read_versions,
)
from .domain import (
    ArtworkManifest,
    FileAudioArtifact,
    FileVideoArtifact,
    LocaleManifest,
    PngImage,
)
from .object_store import ObjectStore
from .thumbnail import make_thumbnail, thumbnail_object_key

UpdateUnit = Literal["artwork", "CN", "EN", "JP", "KR", "TW"]
Manifest = ArtworkManifest | LocaleManifest
BuildManifest = Callable[[str | None, bool], Awaitable[Manifest]]
UpdateStatus = Literal["updated", "unchanged"]

_UNITS = frozenset({"artwork", "CN", "EN", "JP", "KR", "TW"})
_INCOMPLETE_UPSTREAM_LOGGER = logging.getLogger("arkwaifu_updateloop.incomplete_upstream")
_LOGGER = logging.getLogger(__name__)
_THUMBNAIL_WORKERS = os.cpu_count() or 1
_SCORE_ASSET_KINDS = frozenset(
    {
        "icon",
        "logo",
        "background",
        "key-visual",
        "title",
        "decoration",
        "retro-background",
        "divider",
    }
)


@dataclass(frozen=True, slots=True)
class UpdateRequest:
    """Describe one requested dataset and the callback that prepares it.

    Set ``complete`` for an artwork-only historical backfill, including when the published database already records the requested version.
    """

    unit: UpdateUnit
    res_version: str
    build: BuildManifest
    complete: bool = False


@dataclass(frozen=True, slots=True)
class UpdateResult:
    """Report whether one requested dataset changed the published database."""

    unit: UpdateUnit
    res_version: str
    status: UpdateStatus


def _log_artwork_action(
    action: str,
    *,
    version: str,
    status: str,
    resource: str | None = None,
    current: int | None = None,
    total: int | None = None,
    elapsed_seconds: float | None = None,
) -> None:
    """Emit one structured publication event for the artwork unit."""

    extra: dict[str, object] = {
        "action": action,
        "res_version": version,
        "status": status,
    }
    if resource is not None:
        extra["resource"] = resource
    if current is not None:
        extra["current"] = current
    if total is not None:
        extra["total"] = total
    if elapsed_seconds is not None:
        extra["elapsed_ms"] = round(elapsed_seconds * 1000, 3)
    _LOGGER.info("artwork action", extra=extra)


def _prepare_artwork_publication(
    manifests: Sequence[Manifest],
) -> tuple[
    dict[tuple[str, str], str],
    dict[tuple[str, str], str],
    dict[tuple[str, str], str],
    dict[str, str],
    dict[tuple[str, str], str],
    tuple[tuple[str, PngImage], ...],
    tuple[tuple[str, FileVideoArtifact], ...],
    tuple[tuple[str, FileAudioArtifact], ...],
]:
    """Derive object keys and candidate uploads from the requested artwork manifest."""

    manifest = next(
        (manifest for manifest in manifests if isinstance(manifest, ArtworkManifest)),
        None,
    )
    if manifest is None:
        return {}, {}, {}, {}, {}, (), (), ()
    artwork_keys = {
        (artwork.category, artwork.id): image_object_key(
            res_version=artwork.res_version or manifest.upstream_version,
            variant="composition",
            category=artwork.category,
            identifier=artwork.id,
        )
        for artwork in manifest.artworks
    }
    source_layer_keys = {
        (source.category, source.id): image_object_key(
            res_version=source.res_version or manifest.upstream_version,
            variant="source",
            category=source.category,
            identifier=source.id,
        )
        for source in manifest.source_layers
    }
    score_asset_keys = {
        (asset.kind, asset.id): score_asset_object_key(
            res_version=asset.res_version or manifest.upstream_version,
            kind=asset.kind,
            identifier=asset.id,
        )
        for asset in manifest.score_assets
    }
    score_video_keys = {
        video.id: score_video_object_key(
            res_version=video.res_version or manifest.upstream_version,
            identifier=video.id,
        )
        for video in manifest.score_videos
    }
    media_keys = {
        (media.kind, media.id): media_object_key(
            res_version=media.res_version or manifest.upstream_version,
            kind=media.kind,
            identifier=media.id,
            content_type=media.artifact.content_type,
        )
        for media in manifest.media
    }
    png_uploads = tuple(
        [
            (artwork_keys[(artwork.category, artwork.id)], artwork.image)
            for artwork in manifest.artworks
        ]
        + [
            (source_layer_keys[(source.category, source.id)], source.image)
            for source in manifest.source_layers
        ]
        + [
            (score_asset_keys[(asset.kind, asset.id)], asset.image)
            for asset in manifest.score_assets
        ]
    )
    video_uploads = tuple(
        [(score_video_keys[video.id], video.video) for video in manifest.score_videos]
        + [
            (media_keys[(media.kind, media.id)], media.artifact)
            for media in manifest.media
            if isinstance(media.artifact, FileVideoArtifact)
        ]
    )
    audio_uploads = tuple(
        (media_keys[(media.kind, media.id)], media.artifact)
        for media in manifest.media
        if isinstance(media.artifact, FileAudioArtifact)
    )
    return (
        artwork_keys,
        source_layer_keys,
        score_asset_keys,
        score_video_keys,
        media_keys,
        png_uploads,
        video_uploads,
        audio_uploads,
    )


def image_object_key(
    *,
    res_version: str,
    variant: Literal["composition", "source"],
    category: str,
    identifier: str,
) -> str:
    """Return the escaped object key for one final image or material."""

    if not isinstance(res_version, str) or not res_version:
        raise ValueError("artwork resVersion cannot be empty")
    if variant not in {"composition", "source"}:
        raise ValueError(f"unknown image object variant: {variant}")
    if category not in {"illustration", "background", "item", "character"}:
        raise ValueError(f"unknown artwork object category: {category}")
    segments = ("ART", res_version, variant, category, f"{identifier}.png")
    return "/".join(quote(segment, safe="") for segment in segments)


def score_asset_object_key(*, res_version: str, kind: str, identifier: str) -> str:
    """Return the immutable object key for one Score PNG."""

    if not isinstance(res_version, str) or not res_version:
        raise ValueError("artwork resVersion cannot be empty")
    if not isinstance(kind, str) or kind not in _SCORE_ASSET_KINDS:
        raise ValueError(f"unknown Score asset kind: {kind}")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("Score asset identifier cannot be empty")
    segments = ("SCORE", res_version, kind, f"{identifier}.png")
    return "/".join(quote(segment, safe="") for segment in segments)


def score_video_object_key(*, res_version: str, identifier: str) -> str:
    """Return the immutable object key for one Score WebM."""

    if not isinstance(res_version, str) or not res_version:
        raise ValueError("artwork resVersion cannot be empty")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("Score video identifier cannot be empty")
    segments = ("SCORE", res_version, "video", f"{identifier}.webm")
    return "/".join(quote(segment, safe="") for segment in segments)


def media_object_key(*, res_version: str, kind: str, identifier: str, content_type: str) -> str:
    """Return the immutable object key for one story audio or video asset."""

    if not isinstance(res_version, str) or not res_version:
        raise ValueError("artwork resVersion cannot be empty")
    if kind not in {"audio", "video"}:
        raise ValueError(f"unknown media kind: {kind}")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("media identifier must be a nonempty string")
    suffixes = {
        "audio/flac": "flac",
        "audio/wav": "wav",
        "audio/ogg": "ogg",
        "audio/mp4": "m4a",
        "audio/mpeg": "mp3",
        "video/mp4": "mp4",
        "video/quicktime": "mov",
        "video/x-m4v": "m4v",
        "video/webm": "webm",
    }
    try:
        suffix = suffixes[content_type]
    except KeyError as error:
        raise ValueError(f"unsupported media content type: {content_type!r}") from error
    segments = ("MEDIA", res_version, kind, f"{identifier}.{suffix}")
    return "/".join(quote(segment, safe="") for segment in segments)


class Updater:
    """Keep the remote Arkwaifu database and its artwork objects up-to-date."""

    def __init__(self, object_store: ObjectStore, *, upload_workers: int = 16) -> None:
        """Configure publication through one object store."""
        if upload_workers <= 0:
            raise ValueError("upload workers must be positive")
        self._object_store = object_store
        self._upload_workers = upload_workers

    async def run(
        self,
        requests: Sequence[UpdateRequest],
        *,
        force: bool = False,
    ) -> tuple[UpdateResult, ...]:
        """Prepare and publish all requested changes as one operation.

        Builders run concurrently. Successful manifests enter one local SQLite
        transaction, immutable PNG and video winners and derived thumbnails upload
        with bounded concurrency, and the database uploads last. A failure before
        the final upload leaves the previously published database current,
        although immutable creations can remain unreferenced and mutable thumbnails
        can be partially refreshed.
        """

        self._validate_requests(requests)
        if not requests:
            return ()
        if force and any(request.complete for request in requests):
            raise ValueError("complete artwork builds cannot be combined with force")
        if force and any(request.unit == "artwork" for request in requests):
            raise ValueError("force is not supported for artwork updates")

        with tempfile.TemporaryDirectory(prefix="arkwaifu-database-") as temporary:
            database_path = Path(temporary) / "arkwaifu.sqlite3"
            await await_owned(self._object_store.pull_database(database_path))
            database_changed = await await_owned(
                asyncio.to_thread(initialize_or_validate, database_path)
            )
            active_versions = await await_owned(asyncio.to_thread(read_versions, database_path))

            changed_requests = [
                request
                for request in requests
                if force
                or active_versions.get(request.unit) != request.res_version
                or request.complete
            ]
            if not changed_requests:
                if database_changed:
                    await await_owned(self._object_store.push_database(database_path))
                return tuple(
                    UpdateResult(request.unit, request.res_version, "unchanged")
                    for request in requests
                )
            manifests = await self._build_manifests(
                changed_requests,
                active_versions,
                force,
            )
            artwork_manifest = next(
                (manifest for manifest in manifests if isinstance(manifest, ArtworkManifest)),
                None,
            )
            (
                artwork_keys,
                source_layer_keys,
                score_asset_keys,
                score_video_keys,
                media_keys,
                candidate_uploads,
                candidate_video_uploads,
                candidate_audio_uploads,
            ) = _prepare_artwork_publication(manifests)
            apply_started = time.perf_counter()
            try:
                committed_object_keys = await await_owned(
                    asyncio.to_thread(
                        apply_changes,
                        database_path,
                        manifests,
                        artwork_keys=artwork_keys,
                        source_layer_keys=source_layer_keys,
                        score_asset_keys=score_asset_keys,
                        score_video_keys=score_video_keys,
                        media_keys=media_keys,
                    )
                )
            except Exception:
                if artwork_manifest is not None:
                    _log_artwork_action(
                        "apply",
                        version=artwork_manifest.upstream_version,
                        resource="arkwaifu.sqlite3",
                        status="failed",
                        elapsed_seconds=time.perf_counter() - apply_started,
                    )
                raise
            if artwork_manifest is not None:
                _log_artwork_action(
                    "apply",
                    version=artwork_manifest.upstream_version,
                    resource="arkwaifu.sqlite3",
                    status="done",
                    elapsed_seconds=time.perf_counter() - apply_started,
                )
            referenced_uploads = tuple(
                (key, artifact)
                for key, artifact in candidate_uploads
                if key in committed_object_keys
            )
            referenced_video_uploads = tuple(
                (key, artifact)
                for key, artifact in candidate_video_uploads
                if key in committed_object_keys
            )
            if artwork_manifest is None:
                thumbnail_candidates = ()
            else:
                thumbnail_candidates = tuple(
                    (
                        thumbnail_object_key(
                            res_version=artwork.res_version or artwork_manifest.upstream_version,
                            category=artwork.category,
                            identifier=artwork.id,
                        ),
                        artwork.image,
                    )
                    for artwork in artwork_manifest.artworks
                )
            missing = await await_owned(
                asyncio.to_thread(find_missing_artwork_references, database_path)
            )
            if missing:
                _INCOMPLETE_UPSTREAM_LOGGER.warning(
                    "database references unavailable narrative image assets; continuing count=%d sample=%s",
                    len(missing),
                    list(missing[:10]),
                )
            missing_score = await await_owned(
                asyncio.to_thread(find_missing_score_references, database_path)
            )
            if missing_score:
                _INCOMPLETE_UPSTREAM_LOGGER.warning(
                    "database references unavailable presentation assets; continuing count=%d sample=%s",
                    len(missing_score),
                    list(missing_score[:10]),
                )
            missing_media = await await_owned(
                asyncio.to_thread(find_missing_media_references, database_path)
            )
            if missing_media:
                _INCOMPLETE_UPSTREAM_LOGGER.warning(
                    "database references unavailable narrative media assets; continuing count=%d sample=%s",
                    len(missing_media),
                    list(missing_media[:10]),
                )
            await self._upload_artifacts(
                referenced_uploads,
                version=artwork_manifest.upstream_version if artwork_manifest is not None else None,
            )
            await self._upload_videos(
                referenced_video_uploads,
                version=artwork_manifest.upstream_version if artwork_manifest is not None else None,
            )
            referenced_audio_uploads = tuple(
                (key, artifact)
                for key, artifact in candidate_audio_uploads
                if key in committed_object_keys
            )
            await self._upload_audio(
                referenced_audio_uploads,
                version=artwork_manifest.upstream_version if artwork_manifest is not None else None,
            )
            await self._publish_thumbnails(
                thumbnail_candidates,
                version=artwork_manifest.upstream_version if artwork_manifest is not None else None,
            )
            publish_started = time.perf_counter()
            try:
                await await_owned(self._object_store.push_database(database_path))
            except Exception:
                if artwork_manifest is not None:
                    _log_artwork_action(
                        "publish",
                        version=artwork_manifest.upstream_version,
                        resource="arkwaifu.sqlite3",
                        status="failed",
                        elapsed_seconds=time.perf_counter() - publish_started,
                    )
                raise
            if artwork_manifest is not None:
                _log_artwork_action(
                    "publish",
                    version=artwork_manifest.upstream_version,
                    resource="arkwaifu.sqlite3",
                    status="done",
                    elapsed_seconds=time.perf_counter() - publish_started,
                )

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
    def _validate_requests(requests: Sequence[UpdateRequest]) -> None:
        if any(request.complete for request in requests) and (
            len(requests) != 1 or requests[0].unit != "artwork"
        ):
            raise ValueError("complete artwork must be the sole requested update unit")
        seen: set[str] = set()
        for request in requests:
            if request.unit not in _UNITS:
                raise ValueError(f"unknown database unit: {request.unit}")
            if not request.res_version:
                raise ValueError(f"{request.unit} resVersion cannot be empty")
            if request.complete and request.unit != "artwork":
                raise ValueError("complete update policy is available only for artwork")
            if request.unit in seen:
                raise ValueError(f"database unit requested more than once: {request.unit}")
            seen.add(request.unit)

    @staticmethod
    async def _build_manifests(
        requests: Sequence[UpdateRequest],
        active_versions: dict[str, str],
        force: bool,
    ) -> tuple[Manifest, ...]:
        async def build(request: UpdateRequest) -> Manifest:
            manifest = await request.build(active_versions.get(request.unit), force)
            if request.unit == "artwork":
                if not isinstance(manifest, ArtworkManifest):
                    raise TypeError("artwork builder returned a locale manifest")
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
                        ("movements", manifest.movements),
                        ("sections", manifest.sections),
                        ("archive_groups", manifest.archive_groups),
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
        *,
        version: str | None,
    ) -> None:
        """Upload final manifest winners with bounded memory and concurrency."""
        if not uploads:
            return
        numbered_uploads = tuple(enumerate(uploads, start=1))
        iterator = iter(numbered_uploads)
        total = len(numbered_uploads)
        stop = asyncio.Event()
        first_error: Exception | None = None

        async def worker() -> None:
            nonlocal first_error
            while not stop.is_set():
                try:
                    current, (key, artifact) = next(iterator)
                except StopIteration:
                    return
                started = time.perf_counter()
                try:
                    await self._object_store.put_png(key, artifact)
                except Exception as error:  # noqa: BLE001 - adapter errors are opaque
                    if version is not None:
                        _log_artwork_action(
                            "upload",
                            version=version,
                            resource=key,
                            current=current,
                            total=total,
                            status="failed",
                            elapsed_seconds=time.perf_counter() - started,
                        )
                    if first_error is None:
                        first_error = error
                    stop.set()
                    return
                if version is not None:
                    _log_artwork_action(
                        "upload",
                        version=version,
                        resource=key,
                        current=current,
                        total=total,
                        status="done",
                        elapsed_seconds=time.perf_counter() - started,
                    )

        tasks = [
            asyncio.create_task(worker(), name=f"batch-artwork-upload-{index}")
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

    async def _publish_thumbnails(
        self,
        candidates: Sequence[tuple[str, PngImage]],
        *,
        version: str | None,
    ) -> None:
        """Render and upload final winners without retaining the complete batch."""

        if not candidates:
            return
        iterator = iter(enumerate(candidates, start=1))
        total = len(candidates)
        stop = asyncio.Event()
        first_error: Exception | None = None

        async def worker() -> None:
            nonlocal first_error
            while not stop.is_set():
                try:
                    current, (key, source) = next(iterator)
                except StopIteration:
                    return
                started = time.perf_counter()
                try:
                    thumbnail = await asyncio.to_thread(make_thumbnail, source)
                except Exception as error:  # noqa: BLE001 - image decoder errors are opaque
                    if version is not None:
                        _log_artwork_action(
                            "thumbnail",
                            version=version,
                            resource=key,
                            current=current,
                            total=total,
                            status="failed",
                            elapsed_seconds=time.perf_counter() - started,
                        )
                    if first_error is None:
                        first_error = error
                    stop.set()
                    return
                if version is not None:
                    _log_artwork_action(
                        "thumbnail",
                        version=version,
                        resource=key,
                        current=current,
                        total=total,
                        status="done",
                        elapsed_seconds=time.perf_counter() - started,
                    )
                started = time.perf_counter()
                try:
                    await self._object_store.put_thumbnail(key, thumbnail)
                except Exception as error:  # noqa: BLE001 - adapter errors are opaque
                    if version is not None:
                        _log_artwork_action(
                            "upload",
                            version=version,
                            resource=key,
                            current=current,
                            total=total,
                            status="failed",
                            elapsed_seconds=time.perf_counter() - started,
                        )
                    if first_error is None:
                        first_error = error
                    stop.set()
                    return
                if version is not None:
                    _log_artwork_action(
                        "upload",
                        version=version,
                        resource=key,
                        current=current,
                        total=total,
                        status="done",
                        elapsed_seconds=time.perf_counter() - started,
                    )

        tasks = [
            asyncio.create_task(worker(), name=f"thumbnail-publish-{index}")
            for index in range(min(_THUMBNAIL_WORKERS, len(candidates)))
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

    async def _upload_videos(
        self,
        uploads: Sequence[tuple[str, FileVideoArtifact]],
        *,
        version: str | None,
    ) -> None:
        """Upload immutable videos with bounded concurrency."""

        if not uploads:
            return
        iterator = iter(enumerate(uploads, start=1))
        total = len(uploads)
        stop = asyncio.Event()
        first_error: Exception | None = None

        async def worker() -> None:
            nonlocal first_error
            while not stop.is_set():
                try:
                    current, (key, artifact) = next(iterator)
                except StopIteration:
                    return
                started = time.perf_counter()
                try:
                    await self._object_store.put_video(key, artifact)
                except Exception as error:  # noqa: BLE001 - adapter errors are opaque
                    if version is not None:
                        _log_artwork_action(
                            "upload",
                            version=version,
                            resource=key,
                            current=current,
                            total=total,
                            status="failed",
                            elapsed_seconds=time.perf_counter() - started,
                        )
                    if first_error is None:
                        first_error = error
                    stop.set()
                    return
                if version is not None:
                    _log_artwork_action(
                        "upload",
                        version=version,
                        resource=key,
                        current=current,
                        total=total,
                        status="done",
                        elapsed_seconds=time.perf_counter() - started,
                    )

        tasks = [
            asyncio.create_task(worker(), name=f"batch-video-upload-{index}")
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

    async def _upload_audio(
        self,
        uploads: Sequence[tuple[str, FileAudioArtifact]],
        *,
        version: str | None,
    ) -> None:
        """Upload immutable story audio with bounded concurrency."""

        if not uploads:
            return
        iterator = iter(enumerate(uploads, start=1))
        total = len(uploads)
        stop = asyncio.Event()
        first_error: Exception | None = None

        async def worker() -> None:
            nonlocal first_error
            while not stop.is_set():
                try:
                    current, (key, artifact) = next(iterator)
                except StopIteration:
                    return
                started = time.perf_counter()
                try:
                    await self._object_store.put_audio(key, artifact)
                except Exception as error:  # noqa: BLE001 - adapter errors are opaque
                    if version is not None:
                        _log_artwork_action(
                            "upload",
                            version=version,
                            resource=key,
                            current=current,
                            total=total,
                            status="failed",
                            elapsed_seconds=time.perf_counter() - started,
                        )
                    if first_error is None:
                        first_error = error
                    stop.set()
                    return
                if version is not None:
                    _log_artwork_action(
                        "upload",
                        version=version,
                        resource=key,
                        current=current,
                        total=total,
                        status="done",
                        elapsed_seconds=time.perf_counter() - started,
                    )

        tasks = [
            asyncio.create_task(worker(), name=f"batch-audio-upload-{index}")
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
