from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest
from PIL import Image

from arkwaifu_updateloop.art import write_art_manifest
from arkwaifu_updateloop.domain import (
    ArtManifest,
    ArtRecord,
    PngArtifact,
    SourceArtRecord,
)
from arkwaifu_updateloop.upstream import UpstreamCache
from arkwaifu_updateloop.upstream import art as art_module
from arkwaifu_updateloop.upstream.art import (
    UpstreamArtBuilder,
    _bundle_md5,
    _extract_and_render_art_resource,
    _ProcessingStageError,
    _Resource,
)
from arkwaifu_updateloop.upstream.cache import CachedDirectory


def _resource(name: str, content: bytes = b"unity asset bundle") -> _Resource:
    return _Resource(
        name,
        hashlib.md5(content, usedforsecurity=False).hexdigest(),
    )


def _write_wrapper(destination: Path, resource: _Resource, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        archive.writestr(resource.name, content)


def _empty_render(extracted: Path, rendered: Path, version: str) -> None:
    extracted.mkdir(parents=True, exist_ok=True)
    (extracted / "unity-export.txt").write_text("uncomposed", encoding="utf-8")
    write_art_manifest(ArtManifest(version, (), ()), rendered)


@pytest.mark.parametrize(
    ("download_workers", "extraction_workers", "message"),
    [(0, None, "download_workers"), (1, 0, "extraction_workers")],
)
def test_worker_counts_must_be_positive(
    download_workers: int,
    extraction_workers: int | None,
    message: str,
    tmp_path: Path,
):
    with pytest.raises(ValueError, match=message):
        UpstreamArtBuilder(
            version_url="https://example.test/version",
            asset_base_url="https://example.test/assets",
            cache=UpstreamCache(tmp_path / ".cache"),
            download_workers=download_workers,
            extraction_workers=extraction_workers,
        )


def test_art_builder_requires_a_cache_workspace():
    with pytest.raises(TypeError, match="cache"):
        UpstreamArtBuilder(
            version_url="https://example.test/version",
            asset_base_url="https://example.test/assets",
        )


def test_bundle_checksum_uses_the_inner_asset_not_zip_wrapper():
    content = b"unity asset bundle"
    wrapper = BytesIO()
    with ZipFile(wrapper, "w", ZIP_DEFLATED) as archive:
        archive.writestr("avg/bg/example.ab", content)

    assert (
        _bundle_md5(wrapper.getvalue(), "avg/bg/example.ab")
        == hashlib.md5(content, usedforsecurity=False).hexdigest()
    )


def test_bundle_checksum_rejects_a_missing_inner_asset():
    wrapper = BytesIO()
    with ZipFile(wrapper, "w", ZIP_DEFLATED) as archive:
        archive.writestr("other.ab", b"data")

    with pytest.raises(ValueError, match="does not contain"):
        _bundle_md5(wrapper.getvalue(), "expected.ab")


@pytest.mark.parametrize("failing_stage", ["extract", "compose"])
def test_combined_worker_reports_the_stage_that_failed(tmp_path, monkeypatch, failing_stage):
    def extract(_bundles, extracted, *, workers):
        assert workers == 1
        if failing_stage == "extract":
            raise ValueError("cannot extract")
        extracted.mkdir()

    def compose(_extracted, _rendered, _version):
        raise ValueError("cannot compose")

    monkeypatch.setattr(art_module, "extract_assets", extract)
    monkeypatch.setattr(art_module, "_render_art_resource", compose)

    with pytest.raises(_ProcessingStageError) as raised:
        _extract_and_render_art_resource(
            tmp_path / "bundle.ab",
            tmp_path / "extracted",
            tmp_path / "rendered",
            "version",
        )

    assert raised.value.stage == failing_stage
    assert raised.value.elapsed_seconds >= 0
    restored = pickle.loads(pickle.dumps(raised.value))
    assert (restored.stage, restored.elapsed_seconds) == (
        failing_stage,
        raised.value.elapsed_seconds,
    )


@pytest.mark.asyncio
async def test_complete_history_is_additive_and_latest_identity_wins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    image = PngArtifact.from_image(Image.new("RGBA", (1, 1)))
    original = ArtRecord("shared", "image", image)
    replacement_image = PngArtifact.from_image(Image.new("RGBA", (1, 1), (1, 2, 3, 255)))
    replacement = ArtRecord("shared", "image", replacement_image)
    transient = ArtRecord("temporary", "background", image)
    same_id_other_category = ArtRecord("shared", "background", image)
    old_source = SourceArtRecord("source", "char", "body", "1", image)
    new_source = SourceArtRecord(
        "source",
        "char",
        "whole_body",
        "1",
        image,
    )
    manifests = {
        "v1": ArtManifest("v1", (original, transient), (old_source,)),
        "v2": ArtManifest("v2", (replacement,), (new_source,)),
        "v3": ArtManifest("v3", (same_id_other_category,), ()),
    }
    calls = []
    builder = UpstreamArtBuilder(
        version_url="https://example.test/version",
        asset_base_url="https://example.test/assets",
        cache=UpstreamCache(tmp_path / ".cache"),
    )

    async def build(version, active, force):
        calls.append((version, active, force))
        return manifests[version]

    monkeypatch.setattr(builder, "build", build)
    caplog.set_level(logging.INFO, logger=art_module.__name__)

    result = await builder.build_history(("v1", "v2", "v3"))

    assert calls == [
        ("v1", None, False),
        ("v2", "v1", False),
        ("v3", "v2", False),
    ]
    assert result.upstream_version == "v3"
    assert result.arts == (
        replace(same_id_other_category, res_version="v3"),
        replace(transient, res_version="v1"),
        replace(replacement, res_version="v2"),
    )
    assert result.source_arts == (replace(new_source, res_version="v2"),)
    version_records = [
        record for record in caplog.records if getattr(record, "action", None) == "version"
    ]
    assert [(record.res_version, record.status) for record in version_records] == [
        ("v1", "done"),
        ("v2", "done"),
        ("v3", "done"),
    ]
    assert [(record.current, record.total) for record in version_records] == [
        (1, 3),
        (2, 3),
        (3, 3),
    ]
    assert all(record.elapsed_ms >= 0 for record in version_records)


@pytest.mark.asyncio
async def test_cold_fetched_stage_retries_a_corrupt_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    content = b"valid unity asset bundle"
    resource = _resource("avg/images/retry.ab", content)
    wrapper = BytesIO()
    with ZipFile(wrapper, "w", ZIP_DEFLATED) as archive:
        archive.writestr(resource.name, content)
    valid_wrapper = wrapper.getvalue()
    wrapper = BytesIO()
    with ZipFile(wrapper, "w", ZIP_DEFLATED) as archive:
        archive.writestr(resource.name, b"corrupt bundle contents")
    corrupt_wrapper = wrapper.getvalue()
    requests = 0

    def executor_factory(*, max_workers: int | None, max_tasks_per_child: int):
        assert max_tasks_per_child == 1
        return ThreadPoolExecutor(max_workers=max_workers)

    async def respond(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, content=corrupt_wrapper if requests == 1 else valid_wrapper)

    builder = UpstreamArtBuilder(
        version_url="https://example.test/version",
        asset_base_url="https://example.test/assets",
        cache=UpstreamCache(tmp_path / ".cache"),
        extraction_workers=1,
    )

    def process_resource(
        _bundle: Path,
        extracted: Path,
        rendered: Path,
        upstream_version: str,
    ) -> None:
        _empty_render(extracted, rendered, upstream_version)

    monkeypatch.setattr(art_module, "ProcessPoolExecutor", executor_factory)
    monkeypatch.setattr(art_module, "_extract_and_render_art_resource", process_resource)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        manifests = await builder._process_resources(client, "version", [resource])

    assert requests == 2
    assert manifests == [ArtManifest("version", (), ())]
    cached_wrapper = (
        tmp_path
        / ".cache"
        / "version"
        / "art"
        / "resources"
        / "avg%2Fimages%2Fretry.ab"
        / resource.md5
        / "fetched"
        / "wrapper.dat"
    )
    UpstreamArtBuilder._validate_bundle(cached_wrapper, resource)


@pytest.mark.asyncio
async def test_current_gallery_image_bundles_are_selected(tmp_path: Path):
    builder = UpstreamArtBuilder(
        version_url="https://example.test/version",
        asset_base_url="https://x",
        cache=UpstreamCache(tmp_path / ".cache"),
    )

    async def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "abInfos": [
                    {"name": "avg/images/76_i01_2.ab", "md5": "AABB"},
                    {"name": "avg/backgrounds/76_g1.ab", "md5": "BBCC"},
                    {"name": "unrelated/data.ab", "md5": "CCDD"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        resources = await builder._resources(client, "version")

    assert [(resource.name, resource.md5) for resource in resources] == [
        ("avg/backgrounds/76_g1.ab", "bbcc"),
        ("avg/images/76_i01_2.ab", "aabb"),
    ]


@pytest.mark.asyncio
async def test_resource_processing_starts_while_another_download_is_in_flight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    processing_started = threading.Event()
    overlap_observed = False

    def executor_factory(*, max_workers: int | None, max_tasks_per_child: int):
        assert max_tasks_per_child == 1
        return ThreadPoolExecutor(max_workers=max_workers)

    content = b"overlap bundle"

    def process_resource(
        bundle: Path,
        extracted: Path,
        rendered: Path,
        upstream_version: str,
    ) -> None:
        if bundle.name == "first.ab":
            processing_started.set()
        _empty_render(extracted, rendered, upstream_version)

    builder = UpstreamArtBuilder(
        version_url="https://example.test/version",
        asset_base_url="https://example.test/assets",
        cache=UpstreamCache(tmp_path / ".cache"),
        download_workers=2,
        extraction_workers=2,
    )

    async def download(
        _client: httpx.AsyncClient,
        _version: str,
        resource: _Resource,
        destination: Path,
    ) -> Path:
        nonlocal overlap_observed
        if resource.name.endswith("second.ab"):
            overlap_observed = await asyncio.wait_for(
                asyncio.to_thread(processing_started.wait), timeout=2
            )
        _write_wrapper(destination, resource, content)
        return destination

    monkeypatch.setattr(art_module, "ProcessPoolExecutor", executor_factory)
    monkeypatch.setattr(art_module, "_extract_and_render_art_resource", process_resource)
    monkeypatch.setattr(builder, "_download_resource", download)

    resources = [
        _resource("avg/images/first.ab", content),
        _resource("avg/images/second.ab", content),
    ]
    async with httpx.AsyncClient() as client:
        manifests = await builder._process_resources(client, "version", resources)

    assert overlap_observed
    assert len(manifests) == 2


@pytest.mark.asyncio
async def test_resource_processing_concurrency_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    resource_limit = 32
    active = 0
    maximum = 0
    saturated = asyncio.Event()
    release = asyncio.Event()
    cache = UpstreamCache(tmp_path / ".cache")

    async def directory(*_args, **_kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        if active == resource_limit:
            saturated.set()
        try:
            await release.wait()
            return CachedDirectory(
                tmp_path,
                ArtManifest("version", (), ()),
            )
        finally:
            active -= 1

    monkeypatch.setattr(cache, "directory", directory)
    builder = UpstreamArtBuilder(
        version_url="https://example.test/version",
        asset_base_url="https://example.test/assets",
        cache=cache,
    )
    resources = [
        _resource(f"avg/images/resource-{index}.ab") for index in range(resource_limit + 1)
    ]

    async with httpx.AsyncClient() as client:
        operation = asyncio.create_task(builder._process_resources(client, "version", resources))
        await asyncio.wait_for(saturated.wait(), timeout=2)
        await asyncio.sleep(0)
        observed = maximum
        release.set()
        manifests = await operation

    assert observed == resource_limit
    assert len(manifests) == len(resources)


@pytest.mark.asyncio
async def test_build_returns_promoted_file_backed_paths_in_cache_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    content = b"callback bundle"
    resource = _resource("avg/images/callback.ab", content)

    def executor_factory(*, max_workers: int | None, max_tasks_per_child: int):
        assert max_tasks_per_child == 1
        return ThreadPoolExecutor(max_workers=max_workers)

    def process_resource(
        _bundle: Path,
        extracted: Path,
        rendered: Path,
        upstream_version: str,
    ) -> None:
        image = PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255)))
        write_art_manifest(
            ArtManifest(
                upstream_version,
                (ArtRecord("callback", "image", image),),
                (),
            ),
            rendered,
        )
        extracted.mkdir(parents=True, exist_ok=True)

    builder = UpstreamArtBuilder(
        version_url="https://example.test/version",
        asset_base_url="https://example.test/assets",
        cache=UpstreamCache(tmp_path / ".cache"),
        extraction_workers=1,
    )

    async def resources(_client: httpx.AsyncClient, _version: str) -> list[_Resource]:
        return [resource]

    async def download(
        _client: httpx.AsyncClient,
        _version: str,
        selected: _Resource,
        destination: Path,
    ) -> Path:
        _write_wrapper(destination, selected, content)
        return destination

    monkeypatch.setattr(art_module, "ProcessPoolExecutor", executor_factory)
    monkeypatch.setattr(art_module, "_extract_and_render_art_resource", process_resource)
    monkeypatch.setattr(builder, "_resources", resources)
    monkeypatch.setattr(builder, "_download_resource", download)

    merged = await builder.build("version", None, False)

    path = merged.arts[0].image.path
    assert path is not None and path.is_file()
    assert "rendered" in path.parts
    assert "avg%2Fimages%2Fcallback.ab" in path.parts
    assert resource.md5 in path.parts
    resource_root = path.parents[2]
    assert (resource_root / "fetched" / "wrapper.dat").is_file()
    assert (resource_root / "unwrapped" / "avg" / "images" / "callback.ab").is_file()
    assert (resource_root / "extracted").is_dir()


@pytest.mark.asyncio
async def test_staged_cache_retains_inputs_and_render_only_reuses_extracted_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    downloads = 0
    extractions = 0
    renders = 0
    content = b"cached bundle"

    def executor_factory(*, max_workers: int | None, max_tasks_per_child: int):
        assert max_tasks_per_child == 1
        return ThreadPoolExecutor(max_workers=max_workers)

    def process_resource(
        _bundle: Path,
        extracted: Path,
        rendered: Path,
        upstream_version: str,
    ) -> None:
        nonlocal extractions, renders
        extractions += 1
        renders += 1
        _empty_render(extracted, rendered, upstream_version)

    def render_resource(extracted: Path, rendered: Path, upstream_version: str) -> None:
        nonlocal renders
        renders += 1
        assert (extracted / "unity-export.txt").read_text(encoding="utf-8") == "uncomposed"
        write_art_manifest(ArtManifest(upstream_version, (), ()), rendered)

    builder = UpstreamArtBuilder(
        version_url="https://example.test/version",
        asset_base_url="https://example.test/assets",
        extraction_workers=1,
        cache=UpstreamCache(tmp_path / ".cache"),
    )

    async def download(
        _client: httpx.AsyncClient,
        _version: str,
        selected: _Resource,
        destination: Path,
    ) -> Path:
        nonlocal downloads
        downloads += 1
        _write_wrapper(destination, selected, content)
        return destination

    monkeypatch.setattr(art_module, "ProcessPoolExecutor", executor_factory)
    monkeypatch.setattr(art_module, "_extract_and_render_art_resource", process_resource)
    monkeypatch.setattr(art_module, "_render_art_resource", render_resource)
    monkeypatch.setattr(builder, "_download_resource", download)
    resource = _resource("avg/images/cached.ab", content)
    caplog.set_level(logging.INFO, logger=art_module.__name__)

    async with httpx.AsyncClient() as client:
        first = await builder._process_resources(client, "version", [resource])
        second = await builder._process_resources(client, "version", [resource])

    assert downloads == 1
    assert extractions == 1
    assert renders == 1
    assert first[0].arts == second[0].arts
    action_records = [record for record in caplog.records if hasattr(record, "action")]
    assert [(record.action, record.status) for record in action_records] == [
        ("fetch", "done"),
        ("unzip", "done"),
        ("extract", "done"),
        ("compose", "done"),
        ("compose", "cached"),
    ]
    assert all(record.res_version == "version" for record in action_records)
    assert all((record.current, record.total) == (1, 1) for record in action_records)

    resource_path = (
        tmp_path
        / ".cache"
        / "version"
        / "art"
        / "resources"
        / "avg%2Fimages%2Fcached.ab"
        / resource.md5
    )
    assert (resource_path / "fetched" / "wrapper.dat").is_file()
    assert (resource_path / "unwrapped" / "avg" / "images" / "cached.ab").is_file()
    assert (resource_path / "extracted" / "unity-export.txt").is_file()
    assert (resource_path / "rendered" / "manifest.json").is_file()
    for stage in ("fetched", "unwrapped", "extracted", "rendered"):
        assert (resource_path / stage / ".arkwaifu-cache.json").is_file()

    manifest_path = resource_path / "rendered" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["upstream_version"] = "wrong-version"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    prior_action_count = len(action_records)

    async with httpx.AsyncClient() as client:
        manifests = await builder._process_resources(client, "version", [resource])

    assert downloads == 1
    assert extractions == 1
    assert renders == 2
    assert manifests[0].upstream_version == "version"
    assert manifests[0].arts == ()
    assert manifests[0].source_arts == ()
    rerender_records = [record for record in caplog.records if hasattr(record, "action")][
        prior_action_count:
    ]
    assert [(record.action, record.status) for record in rerender_records] == [
        ("extract", "cached"),
        ("compose", "done"),
    ]

    changed_content = b"changed cached bundle"
    changed = _resource(resource.name, changed_content)
    content = changed_content
    async with httpx.AsyncClient() as client:
        await builder._process_resources(client, "version", [changed])

    changed_path = resource_path.parent / changed.md5
    assert (resource_path / "rendered" / "manifest.json").is_file()
    assert (changed_path / "rendered" / "manifest.json").is_file()
    assert downloads == 2
    assert extractions == 2
    assert renders == 3
