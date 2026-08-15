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

Resource pipelines, downloads, and extraction processes each have their own
concurrency bound.
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
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, cast
from urllib.parse import quote

import httpx

from ..art import (
    IvfMetadata,
    add_gallery_composites,
    build_art_manifest,
    demux_usm_to_ivf,
    merge_art_manifests,
    read_art_manifest,
    remux_ivf_to_webm,
    validate_ivf,
    write_art_manifest,
)
from ..asyncio_tools import await_owned
from ..domain import (
    ArtCategory,
    ArtManifest,
    CompositePanel,
    CompositeType,
    GalleryArtwork,
    ScoreVideoRecord,
)
from ..extraction import extract_assets
from .cache import UpstreamCache

_ART_PATTERNS = (
    "avg/imgs/**",
    "avg/images/**",
    "avg/bg/**",
    "avg/backgrounds/**",
    "avg/items/**",
    "avg/characters/**",
    "arts/ui/mixstory/**",
    "spritepack/mixstory_*.ab",
    "raw/video/mixstory/*.usm",
)
# A resource may hold one lock for each cache stage while it is materialized.
# Bound the complete pipeline so a cold all-resource run cannot exhaust file handles.
_ART_RESOURCE_WORKERS = 32
# Bump a stage when its persisted layout or recipe changes. Each fingerprint
# includes earlier formats, so changing one stage also invalidates its dependents.
_ART_STAGE_FORMATS = {
    "fetched": "1",
    "unwrapped": "1",
    "extracted": "1",
    "rendered": "5",
}
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _Resource:
    """Identify one asset bundle by its upstream name and integrity checksum."""

    name: str
    md5: str


@dataclass(frozen=True, slots=True)
class _ProcessingTimings:
    """Measure the two operations performed by one disposable child process."""

    extract_seconds: float
    compose_seconds: float


@dataclass(frozen=True, slots=True)
class _GalleryRecipes:
    """Hold one branch-consistent, picklable CN gallery recipe catalog."""

    version: str
    digest: str
    recipes: tuple[GalleryArtwork, ...]

    @property
    def cache_identity(self) -> str:
        return f"{self.version}:{self.digest}"


class _ProcessingStageError(RuntimeError):
    """Carry the failing child-process stage across the process boundary."""

    def __init__(self, stage: str, detail: str, elapsed_seconds: float) -> None:
        self.stage = stage
        self.elapsed_seconds = elapsed_seconds
        super().__init__(stage, detail, elapsed_seconds)


def _normalized_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key.lower(): item for key, item in value.items() if isinstance(key, str)}


def _declared_gallery_identifier(
    value: dict[str, Any],
    field: str,
    mapping_key: str,
    context: str,
) -> str:
    declared = value.get(field)
    if not isinstance(declared, str) or not declared:
        raise ValueError(f"{context} has an invalid {field}: {declared!r}")
    identifier = declared.lower()
    if identifier != mapping_key.lower():
        raise ValueError(
            f"{context} mapping key does not match {field}: "
            f"key={mapping_key.lower()} declared={identifier}"
        )
    return identifier


def _string_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str) and item)
    if isinstance(value, dict):
        return tuple(item for item in value.values() if isinstance(item, str) and item)
    return ()


def _log_art_action(
    action: str,
    *,
    version: str,
    status: str,
    resource: str | None = None,
    current: int | None = None,
    total: int | None = None,
    elapsed_seconds: float | None = None,
) -> None:
    """Emit one structured, resource-stable art pipeline event."""

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
    _LOGGER.info("art action", extra=extra)


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
    recipes: tuple[GalleryArtwork, ...] = (),
) -> None:
    """Process one extracted resource and write its file-backed manifest."""

    manifest = add_gallery_composites(
        build_art_manifest(extracted, upstream_version),
        recipes,
    )
    write_art_manifest(manifest, rendered)


def _extract_and_render_art_resource(
    bundle: Path,
    extracted: Path,
    rendered: Path,
    upstream_version: str,
    recipes: tuple[GalleryArtwork, ...] = (),
) -> _ProcessingTimings:
    """Populate both expensive stages in one disposable child on a cold miss."""
    started = time.perf_counter()
    try:
        extract_assets([bundle], extracted, workers=1)
    except Exception as error:
        raise _ProcessingStageError(
            "extract",
            str(error),
            time.perf_counter() - started,
        ) from error
    extracted_at = time.perf_counter()
    try:
        _render_art_resource(extracted, rendered, upstream_version, recipes)
    except Exception as error:
        raise _ProcessingStageError(
            "compose",
            str(error),
            time.perf_counter() - extracted_at,
        ) from error
    completed_at = time.perf_counter()
    return _ProcessingTimings(
        extract_seconds=extracted_at - started,
        compose_seconds=completed_at - extracted_at,
    )


def _extract_score_video(source: Path, extracted: Path) -> IvfMetadata:
    metadata = demux_usm_to_ivf(source, extracted / "video.ivf")
    (extracted / "metadata.json").write_text(
        json.dumps(
            {
                "width": metadata.width,
                "height": metadata.height,
                "frame_rate_numerator": metadata.frame_rate_numerator,
                "frame_rate_denominator": metadata.frame_rate_denominator,
                "frame_count": metadata.frame_count,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return metadata


def _read_score_video_metadata(extracted: Path) -> IvfMetadata:
    payload = json.loads((extracted / "metadata.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("Score IVF metadata is not an object")
    values = []
    for name in (
        "width",
        "height",
        "frame_rate_numerator",
        "frame_rate_denominator",
        "frame_count",
    ):
        value = payload.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"Score IVF metadata has invalid {name}: {value!r}")
        values.append(value)
    metadata = IvfMetadata(*values)
    if validate_ivf((extracted / "video.ivf").read_bytes()) != metadata:
        raise ValueError("Score IVF metadata does not match its stream")
    return metadata


def _render_score_video(
    extracted: Path,
    rendered: Path,
    upstream_version: str,
    video_id: str,
) -> None:
    metadata = _read_score_video_metadata(extracted)
    artifact = remux_ivf_to_webm(
        extracted / "video.ivf",
        rendered / "processed/00000000.webm",
        metadata,
    )
    write_art_manifest(
        ArtManifest(
            upstream_version,
            (),
            (),
            score_videos=(ScoreVideoRecord(video_id, artifact),),
        ),
        rendered,
    )


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


def _stage_fingerprint(
    stage: str,
    resource: _Resource,
    gallery_recipes: _GalleryRecipes | None = None,
) -> str:
    """Describe every input format on which a cached stage depends.

    Changing an early format invalidates that stage and every stage after it,
    while leaving independent resources and earlier compatible work reusable.
    """

    stage_order = tuple(_ART_STAGE_FORMATS)
    dependency_formats = {
        name: _ART_STAGE_FORMATS[name] for name in stage_order[: stage_order.index(stage) + 1]
    }
    payload = {
        "formats": dependency_formats,
        "resource": resource.name,
        "md5": resource.md5,
    }
    if stage == "rendered" and gallery_recipes is not None:
        payload["gallery_recipes"] = gallery_recipes.cache_identity
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )


class UpstreamArtBuilder:
    """Fetch and build an art delta for one detected upstream version.

    Unless forced, the builder processes only bundles whose name or published MD5 changed. The published database retains unchanged art.
    """

    def __init__(
        self,
        *,
        version_url: str,
        asset_base_url: str,
        cache: UpstreamCache,
        gallery_metadata_base_url: str | None = None,
        download_workers: int = 16,
        extraction_workers: int | None = None,
    ) -> None:
        """Configure Windows art downloads, caching, and processing limits."""
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
        self._gallery_metadata_base_url = (
            gallery_metadata_base_url.rstrip("/") if gallery_metadata_base_url else None
        )
        self._gallery_recipes_task: asyncio.Task[_GalleryRecipes] | None = None

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
            gallery_recipes = await self._load_gallery_recipes(client)
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
                await self._process_resources(
                    client,
                    upstream_version,
                    selected,
                    gallery_recipes,
                )
                if selected
                else []
            )
        return merge_art_manifests(manifests, upstream_version)

    async def build_history(self, versions: tuple[str, ...]) -> ArtManifest:
        """Build every recorded version as one additive, latest-wins manifest.

        The earliest version is a full build. Each later version compares only
        with its immediate predecessor, so bundles temporarily published and
        later removed remain in the cumulative result. Repeated art identities
        are replaced by the newest version that contains them.
        """

        if not versions:
            raise ValueError("art version history cannot be empty")
        if any(not isinstance(version, str) or not version for version in versions):
            raise ValueError("art version history contains an invalid resVersion")
        if len(set(versions)) != len(versions):
            raise ValueError("art version history contains a duplicate resVersion")

        arts = {}
        sources = {}
        score_assets = {}
        score_videos = {}
        previous: str | None = None
        total = len(versions)
        for current, version in enumerate(versions, start=1):
            started = time.perf_counter()
            try:
                manifest = await self.build(version, previous, False)
            except Exception:
                _log_art_action(
                    "version",
                    version=version,
                    status="failed",
                    current=current,
                    total=total,
                    elapsed_seconds=time.perf_counter() - started,
                )
                raise
            arts.update(
                {
                    (art.category, art.id): replace(
                        art,
                        res_version=art.res_version or manifest.upstream_version,
                    )
                    for art in manifest.arts
                }
            )
            sources.update(
                {
                    (source.category, source.id): replace(
                        source,
                        res_version=source.res_version or manifest.upstream_version,
                    )
                    for source in manifest.source_arts
                }
            )
            score_assets.update(
                {
                    (asset.kind, asset.id): replace(
                        asset,
                        res_version=asset.res_version or manifest.upstream_version,
                    )
                    for asset in manifest.score_assets
                }
            )
            score_videos.update(
                {
                    video.id: replace(
                        video,
                        res_version=video.res_version or manifest.upstream_version,
                    )
                    for video in manifest.score_videos
                }
            )
            _log_art_action(
                "version",
                version=version,
                status="done",
                current=current,
                total=total,
                elapsed_seconds=time.perf_counter() - started,
            )
            previous = version
        return ArtManifest(
            upstream_version=versions[-1],
            arts=tuple(sorted(arts.values(), key=lambda art: (art.category, art.id))),
            source_arts=tuple(
                sorted(sources.values(), key=lambda source: (source.category, source.id))
            ),
            score_assets=tuple(
                sorted(score_assets.values(), key=lambda asset: (asset.kind, asset.id))
            ),
            score_videos=tuple(sorted(score_videos.values(), key=lambda video: video.id)),
        )

    async def _resources(self, client: httpx.AsyncClient, version: str) -> list[_Resource]:
        """Get the cached hot-update list for one resource version."""

        url = f"{self._asset_base_url}/{quote(version, safe='')}/hot_update_list.json"

        async def fetch(destination: Path) -> None:
            started = time.perf_counter()
            try:
                response = await client.get(url)
                response.raise_for_status()
                destination.write_bytes(response.content)
            except Exception:
                _log_art_action(
                    "list",
                    version=version,
                    resource="hot_update_list.json",
                    current=1,
                    total=1,
                    status="failed",
                    elapsed_seconds=time.perf_counter() - started,
                )
                raise
            _log_art_action(
                "list",
                version=version,
                resource="hot_update_list.json",
                current=1,
                total=1,
                status="done",
                elapsed_seconds=time.perf_counter() - started,
            )

        path = await self._cache.file(
            version,
            PurePosixPath("art", "hot_update_list.json"),
            fetch,
            self._validate_resource_list,
            on_hit=lambda: _log_art_action(
                "list",
                version=version,
                resource="hot_update_list.json",
                current=1,
                total=1,
                status="cached",
            ),
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self._parse_resources(payload, version)

    async def _load_gallery_recipes(
        self,
        client: httpx.AsyncClient,
    ) -> _GalleryRecipes:
        task = self._gallery_recipes_task
        if task is None:
            task = asyncio.create_task(
                self._fetch_gallery_recipes(client),
                name="fetch-cn-gallery-recipes",
            )
            self._gallery_recipes_task = task
        try:
            return await asyncio.shield(task)
        except BaseException:
            if self._gallery_recipes_task is task:
                self._gallery_recipes_task = None
            raise

    async def _fetch_gallery_recipes(
        self,
        client: httpx.AsyncClient,
    ) -> _GalleryRecipes:
        """Fetch one branch-consistent CN recipe catalog once per art build."""

        if self._gallery_metadata_base_url is None:
            return _GalleryRecipes("disabled", "none", ())
        version_url = f"{self._gallery_metadata_base_url}/hot_update_list.json"
        stage_url = f"{self._gallery_metadata_base_url}/gamedata/excel/stage_table.json"

        async def version() -> str:
            response = await client.get(version_url, headers={"Cache-Control": "no-cache"})
            response.raise_for_status()
            payload = response.json()
            value = payload.get("versionId") if isinstance(payload, dict) else None
            if not isinstance(value, str) or not value:
                raise ValueError("CN gallery metadata does not contain versionId")
            return value

        before = await version()
        response = await client.get(stage_url, headers={"Cache-Control": "no-cache"})
        response.raise_for_status()
        content = response.content
        after = await version()
        if before != after:
            raise RuntimeError(
                f"CN gallery metadata changed during art preparation: {before} to {after}"
            )
        digest = hashlib.sha256(content).hexdigest()

        async def materialize(destination: Path) -> None:
            await await_owned(asyncio.to_thread(destination.write_bytes, content))

        def validate(path: Path) -> tuple[GalleryArtwork, ...]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError(f"invalid cached CN gallery metadata: {error}") from error
            return self._parse_gallery_recipes(payload)

        cached = await self._cache.file(
            before,
            PurePosixPath("art", "gallery-recipes", f"{digest}.json"),
            materialize,
            validate,
        )
        recipes = validate(cached)
        return _GalleryRecipes(before, digest, recipes)

    @staticmethod
    def _parse_gallery_recipes(payload: object) -> tuple[GalleryArtwork, ...]:
        """Normalize category-qualified composite recipes from stage metadata."""

        if not isinstance(payload, dict):
            raise TypeError("CN stage_table.json is not an object")
        displays = _normalized_mapping(payload.get("cgGalleryDisplays"))
        cgs = _normalized_mapping(payload.get("cgGalleryCgs"))
        categories: dict[str, ArtCategory] = {}
        for display_key, raw_display in displays.items():
            if not isinstance(raw_display, dict):
                raise TypeError(f"gallery display is not an object: {display_key}")
            display_id = _declared_gallery_identifier(
                raw_display,
                "displayId",
                display_key,
                "gallery display",
            )
            source = raw_display.get("cgSource")
            if not isinstance(source, str) or source.upper() not in {
                "IMAGE",
                "BACKGROUND",
            }:
                raise ValueError(f"gallery display has unknown cgSource: {display_id}={source!r}")
            category: ArtCategory = "background" if source.upper() == "BACKGROUND" else "image"
            for raw_id in _string_values(raw_display.get("cgList")):
                cg_id = raw_id.lower()
                if cg_id not in cgs:
                    raise ValueError(f"gallery artwork is not declared: {cg_id}")
                previous = categories.get(cg_id)
                if previous is not None and previous != category:
                    raise ValueError(f"gallery CG has conflicting source categories: {cg_id}")
                categories[cg_id] = category

        recipes = []
        for raw_id, raw_value in cgs.items():
            if not isinstance(raw_value, dict):
                raise TypeError(f"gallery artwork is not an object: {raw_id}")
            raw = raw_value
            cg_id = _declared_gallery_identifier(
                raw,
                "cgId",
                raw_id,
                "gallery artwork",
            )
            raw_composite_type = raw.get("compositeType")
            if not isinstance(raw_composite_type, str):
                raise TypeError(f"gallery artwork has no compositeType: {cg_id}")
            composite_type = raw_composite_type.lower()
            if composite_type == "none":
                continue
            if composite_type not in {"vertical", "horizontal"}:
                raise ValueError(f"unknown gallery composite type: {composite_type!r}")
            category = categories.get(cg_id)
            if category is None:
                raise ValueError(f"gallery composite is not referenced by a display: {cg_id}")
            raw_panels = raw.get("compositeList")
            if not isinstance(raw_panels, list) or not raw_panels:
                raise ValueError(f"gallery composite has no panels: {cg_id}")
            panels = []
            for position, raw_panel in enumerate(raw_panels):
                if not isinstance(raw_panel, dict):
                    raise TypeError(f"gallery composite panel is not an object: {cg_id}")
                panel_id = raw_panel.get("cgId")
                width = raw_panel.get("width")
                height = raw_panel.get("height")
                if not isinstance(panel_id, str) or not panel_id:
                    raise ValueError(f"gallery composite has an invalid panel ID: {cg_id}")
                if "/" in panel_id:
                    raise ValueError(
                        f"gallery composite panel ID contains reserved '/': {panel_id!r}"
                    )
                if (
                    not isinstance(width, int)
                    or isinstance(width, bool)
                    or width <= 0
                    or not isinstance(height, int)
                    or isinstance(height, bool)
                    or height <= 0
                ):
                    raise ValueError(f"gallery composite has invalid dimensions: {cg_id}")
                panels.append(CompositePanel(panel_id.lower(), position, width, height))
            recipes.append(
                GalleryArtwork(
                    position=int(raw.get("sortId", 0)),
                    cg_id=cg_id,
                    art_id="/".join(panel.id for panel in panels),
                    category=category,
                    composite_type=cast(CompositeType, composite_type),
                    panels=tuple(panels),
                )
            )
        return tuple(sorted(recipes, key=lambda recipe: (recipe.category, recipe.art_id)))

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
        gallery_recipes: _GalleryRecipes | None = None,
    ) -> list[ArtManifest]:
        """Run selected resources concurrently without unbounded cache locks."""

        gallery_recipes = gallery_recipes or _GalleryRecipes("disabled", "none", ())

        resource_semaphore = asyncio.Semaphore(_ART_RESOURCE_WORKERS)
        download_semaphore = asyncio.Semaphore(self._download_workers)
        loop = asyncio.get_running_loop()
        executor = ProcessPoolExecutor(
            max_workers=self._extraction_workers,
            max_tasks_per_child=1,
        )

        total = len(resources)

        async def process_one(resource: _Resource, current: int) -> ArtManifest:
            resource_root = _resource_cache_path(resource)

            def log(
                action: str,
                status: str,
                elapsed_seconds: float | None = None,
            ) -> None:
                _log_art_action(
                    action,
                    version=version,
                    resource=resource.name,
                    current=current,
                    total=total,
                    status=status,
                    elapsed_seconds=elapsed_seconds,
                )

            def validate_rendered(destination: Path) -> ArtManifest:
                manifest = read_art_manifest(destination)
                if manifest.upstream_version != version:
                    raise ValueError(
                        "rendered art resource has the wrong upstream version: "
                        f"{manifest.upstream_version!r}, expected {version!r}"
                    )
                return manifest

            if resource.name.endswith(".usm"):
                video_id = PurePosixPath(resource.name).stem.lower()

                async def materialize_video_rendered(rendered: Path) -> None:
                    async def materialize_video_extracted(extracted: Path) -> None:
                        async def materialize_video_unwrapped(unwrapped: Path) -> None:
                            async def materialize_video_fetched(fetched: Path) -> None:
                                async with download_semaphore:
                                    started = time.perf_counter()
                                    try:
                                        await self._download_resource(
                                            client,
                                            version,
                                            resource,
                                            fetched / "wrapper.dat",
                                        )
                                    except Exception:
                                        log("fetch", "failed", time.perf_counter() - started)
                                        raise
                                log("fetch", "done", time.perf_counter() - started)

                            fetched = await self._cache.directory(
                                version,
                                resource_root / "fetched",
                                _stage_fingerprint("fetched", resource),
                                materialize_video_fetched,
                                lambda path: self._validate_fetched(path, resource),
                                on_hit=lambda: log("fetch", "cached"),
                            )
                            started = time.perf_counter()
                            await await_owned(
                                asyncio.to_thread(
                                    _unzip_resource,
                                    fetched.path / "wrapper.dat",
                                    resource.name,
                                    unwrapped,
                                )
                            )
                            log("unzip", "done", time.perf_counter() - started)

                        unwrapped = await self._cache.directory(
                            version,
                            resource_root / "unwrapped",
                            _stage_fingerprint("unwrapped", resource),
                            materialize_video_unwrapped,
                            lambda path: self._validate_unwrapped(path, resource),
                            on_hit=lambda: log("unzip", "cached"),
                        )
                        started = time.perf_counter()
                        source = unwrapped.path.joinpath(
                            *_resource_member_path(resource.name).parts
                        )
                        await await_owned(
                            asyncio.to_thread(_extract_score_video, source, extracted)
                        )
                        log("extract", "done", time.perf_counter() - started)

                    extracted = await self._cache.directory(
                        version,
                        resource_root / "extracted",
                        _stage_fingerprint("extracted", resource),
                        materialize_video_extracted,
                        _read_score_video_metadata,
                        on_hit=lambda: log("extract", "cached"),
                    )
                    started = time.perf_counter()
                    await await_owned(
                        asyncio.to_thread(
                            _render_score_video,
                            extracted.path,
                            rendered,
                            version,
                            video_id,
                        )
                    )
                    log("compose", "done", time.perf_counter() - started)

                rendered_video = await self._cache.directory(
                    version,
                    resource_root / "rendered",
                    _stage_fingerprint("rendered", resource),
                    materialize_video_rendered,
                    validate_rendered,
                    on_hit=lambda: log("compose", "cached"),
                )
                if not isinstance(rendered_video.value, ArtManifest):
                    raise TypeError(f"rendered Score video has no manifest: {rendered_video.path}")
                return rendered_video.value

            async def materialize_rendered(rendered: Path) -> None:
                rendered_by_extractor = False

                async def materialize_extracted(extracted: Path) -> None:
                    nonlocal rendered_by_extractor

                    async def materialize_unwrapped(unwrapped: Path) -> None:
                        async def materialize_fetched(fetched: Path) -> None:
                            async with download_semaphore:
                                started = time.perf_counter()
                                try:
                                    await self._download_resource(
                                        client,
                                        version,
                                        resource,
                                        fetched / "wrapper.dat",
                                    )
                                except Exception:
                                    log("fetch", "failed", time.perf_counter() - started)
                                    raise
                            log("fetch", "done", time.perf_counter() - started)

                        fetched = await self._cache.directory(
                            version,
                            resource_root / "fetched",
                            _stage_fingerprint("fetched", resource),
                            materialize_fetched,
                            lambda path: self._validate_fetched(path, resource),
                            on_hit=lambda: log("fetch", "cached"),
                        )
                        started = time.perf_counter()
                        try:
                            await await_owned(
                                asyncio.to_thread(
                                    _unzip_resource,
                                    fetched.path / "wrapper.dat",
                                    resource.name,
                                    unwrapped,
                                )
                            )
                        except Exception:
                            log("unzip", "failed", time.perf_counter() - started)
                            raise
                        log("unzip", "done", time.perf_counter() - started)

                    unwrapped = await self._cache.directory(
                        version,
                        resource_root / "unwrapped",
                        _stage_fingerprint("unwrapped", resource),
                        materialize_unwrapped,
                        lambda path: self._validate_unwrapped(path, resource),
                        on_hit=lambda: log("unzip", "cached"),
                    )
                    bundle = unwrapped.path.joinpath(*_resource_member_path(resource.name).parts)
                    try:
                        timings = await await_owned(
                            loop.run_in_executor(
                                executor,
                                _extract_and_render_art_resource,
                                bundle,
                                extracted,
                                rendered,
                                version,
                                gallery_recipes.recipes,
                            )
                        )
                    except _ProcessingStageError as error:
                        log(error.stage, "failed", error.elapsed_seconds)
                        raise
                    if isinstance(timings, _ProcessingTimings):
                        log("extract", "done", timings.extract_seconds)
                        log("compose", "done", timings.compose_seconds)
                    else:
                        # Test doubles and third-party executors may not return timings.
                        log("extract", "done")
                        log("compose", "done")
                    rendered_by_extractor = True

                extracted = await self._cache.directory(
                    version,
                    resource_root / "extracted",
                    _stage_fingerprint("extracted", resource),
                    materialize_extracted,
                    self._validate_extracted,
                    on_hit=lambda: log("extract", "cached"),
                )
                if not rendered_by_extractor:
                    started = time.perf_counter()
                    try:
                        await await_owned(
                            loop.run_in_executor(
                                executor,
                                _render_art_resource,
                                extracted.path,
                                rendered,
                                version,
                                gallery_recipes.recipes,
                            )
                        )
                    except Exception:
                        log("compose", "failed", time.perf_counter() - started)
                        raise
                    log("compose", "done", time.perf_counter() - started)

            rendered = await self._cache.directory(
                version,
                resource_root / "rendered",
                _stage_fingerprint("rendered", resource, gallery_recipes),
                materialize_rendered,
                validate_rendered,
                on_hit=lambda: log("compose", "cached"),
            )
            if not isinstance(rendered.value, ArtManifest):
                raise TypeError(f"rendered art resource has no manifest: {rendered.path}")
            return rendered.value

        async def process(resource: _Resource, current: int) -> ArtManifest:
            async with resource_semaphore:
                return await process_one(resource, current)

        tasks = [
            asyncio.create_task(process(resource, current))
            for current, resource in enumerate(resources, start=1)
        ]
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
            "art pipeline completed resources=%s resource_workers=%s download_workers=%s extraction_workers=%s",
            len(resources),
            _ART_RESOURCE_WORKERS,
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
        UpstreamArtBuilder._validate_bundle(wrapper, resource)
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
