import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from arkwaifu_updateloop import UpdateRequest, UpdateResult, cli
from arkwaifu_updateloop.domain import ArtManifest, ArtRecord, FilePngArtifact, LocaleManifest
from arkwaifu_updateloop.upstream import UpstreamCache


class _FakeUpdater:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[UpdateRequest, ...], bool]] = []

    async def run(self, requests, *, force=False):
        values = tuple(requests)
        self.calls.append((values, force))
        return tuple(UpdateResult(value.unit, value.res_version, "updated") for value in values)


class _FakeLocaleBuilder:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def _patch_runtime(monkeypatch: pytest.MonkeyPatch) -> _FakeUpdater:
    settings = object()
    updater = _FakeUpdater()
    locale_builder = _FakeLocaleBuilder()
    monkeypatch.setattr(cli.Settings, "from_environment", staticmethod(lambda: settings))
    monkeypatch.setattr(cli, "_updater", lambda received: updater)
    monkeypatch.setattr(cli, "_locale_builder", lambda settings, cache: locale_builder)
    return updater


async def _wait_for(event: asyncio.Event) -> None:
    await asyncio.wait_for(event.wait(), timeout=2)


def _request(unit: str) -> UpdateRequest:
    async def build(_active: str | None, _force: bool):
        if unit == "art":
            return ArtManifest(f"{unit}-v1", (), ())
        return LocaleManifest(unit, f"{unit}-v1", (), ())

    return UpdateRequest(unit, f"{unit}-v1", build)


@pytest.mark.asyncio
async def test_run_starts_all_version_preparations_concurrently(monkeypatch):
    updater = _patch_runtime(monkeypatch)
    preparation_gate = asyncio.Event()
    all_preparations_started = asyncio.Event()
    started: set[str] = set()
    locale_builders: set[int] = set()
    requested = {"art", "EN", "JP"}

    async def prepare(unit: str):
        started.add(unit)
        if started == requested:
            all_preparations_started.set()
        await preparation_gate.wait()
        return _request(unit)

    def prepare_locale(builder, unit):
        locale_builders.add(id(builder))
        return prepare(unit)

    monkeypatch.setattr(cli, "_prepare_art", lambda settings, cache: prepare("art"))
    monkeypatch.setattr(cli, "_prepare_locale", prepare_locale)

    run = asyncio.create_task(cli._run(["art", "EN", "JP"], force=False, use_cache=False))
    await _wait_for(all_preparations_started)

    assert started == requested
    assert len(locale_builders) == 1
    assert not run.done()
    preparation_gate.set()
    assert await run == 0
    assert [request.unit for request in updater.calls[0][0]] == ["art", "EN", "JP"]


@pytest.mark.asyncio
async def test_run_passes_force_to_a_locale_only_publication(monkeypatch):
    updater = _patch_runtime(monkeypatch)
    monkeypatch.setattr(
        cli,
        "_prepare_locale",
        lambda builder, unit: _ready(_request(unit)),
    )

    assert await cli._run(["EN", "JP"], force=True, use_cache=False) == 0

    assert len(updater.calls) == 1
    requests, force = updater.calls[0]
    assert [request.unit for request in requests] == ["EN", "JP"]
    assert force is True


async def _ready(value):
    return value


@pytest.mark.asyncio
async def test_any_preparation_failure_prevents_database_publication(monkeypatch, caplog):
    updater = _patch_runtime(monkeypatch)

    async def fail(settings, cache):
        raise RuntimeError("art version failed")

    monkeypatch.setattr(cli, "_prepare_art", fail)
    monkeypatch.setattr(
        cli,
        "_prepare_locale",
        lambda builder, unit: _ready(_request(unit)),
    )

    with caplog.at_level("ERROR"):
        result = await cli._run(["art", "EN", "JP"], force=False, use_cache=False)

    assert result == 1
    assert updater.calls == []
    assert "unit=art status=failed" in caplog.text


@pytest.mark.asyncio
async def test_database_failure_returns_nonzero_without_a_second_attempt(monkeypatch, caplog):
    updater = _patch_runtime(monkeypatch)

    async def fail(requests, *, force=False):
        updater.calls.append((tuple(requests), force))
        raise RuntimeError("database upload failed")

    updater.run = fail
    monkeypatch.setattr(cli, "_prepare_art", lambda settings, cache: _ready(_request("art")))

    with caplog.at_level("ERROR"):
        result = await cli._run(["art"], force=False, use_cache=False)

    assert result == 1
    assert len(updater.calls) == 1
    assert "database status=failed" in caplog.text


@pytest.mark.asyncio
async def test_prepare_art_exposes_one_batch_build(monkeypatch, tmp_path: Path):
    resource = ArtManifest("art-v1", (), ())
    cache = UpstreamCache(tmp_path / ".cache")

    class Builder:
        def __init__(self, **kwargs) -> None:
            assert kwargs["cache"] is cache
            assert kwargs["gallery_metadata_base_url"] == (
                "https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/master/cn"
            )

        async def detect_version(self):
            return "art-v1"

        async def build(self, upstream_version, active_version, force):
            assert (upstream_version, active_version, force) == ("art-v1", None, False)
            return resource

    monkeypatch.setattr(cli, "UpstreamArtBuilder", Builder)
    settings = SimpleNamespace(
        art_version_url="https://version.example",
        art_asset_base_url="https://assets.example",
        download_workers=2,
        extraction_workers=1,
    )
    update = await cli._prepare_art(settings, cache)
    manifest = await update.build(None, False)

    assert manifest is resource


@pytest.mark.asyncio
async def test_prepare_complete_art_uses_history_builder_once(monkeypatch, tmp_path: Path):
    resource = ArtManifest("art-v3", (), ())
    cache = UpstreamCache(tmp_path / ".cache")
    calls = []

    class Builder:
        def __init__(self, **kwargs) -> None:
            assert kwargs["cache"] is cache
            assert kwargs["gallery_metadata_base_url"] == (
                "https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/master/cn"
            )

        async def detect_version(self):
            return "art-v3"

        async def build_history(self, versions):
            calls.append(versions)
            return resource

    class History:
        def __init__(self, **kwargs) -> None:
            assert kwargs["cache"] is cache

        async def versions(self, current):
            assert current == "art-v3"
            return ("art-v1", "art-v2", "art-v3")

    monkeypatch.setattr(cli, "UpstreamArtBuilder", Builder)
    monkeypatch.setattr(cli, "WindowsVersionHistory", History)
    settings = SimpleNamespace(
        art_version_url="https://version.example",
        art_asset_base_url="https://assets.example",
        github_api_url="https://api.github.example",
        github_token=None,
        download_workers=2,
        extraction_workers=1,
    )

    update = await cli._prepare_art(settings, cache, complete=True)
    manifest = await update.build("art-v3", False)

    assert update.complete is True
    assert manifest is resource
    assert calls == [("art-v1", "art-v2", "art-v3")]


@pytest.mark.asyncio
async def test_prepare_complete_art_archives_the_same_history_before_build(
    monkeypatch,
    tmp_path: Path,
):
    resource = ArtManifest("art-v2", (), ())
    cache = UpstreamCache(tmp_path / ".cache")
    calls = []
    archive_store = object()

    class Builder:
        def __init__(self, **_kwargs) -> None:
            pass

        async def detect_version(self):
            return "art-v2"

        async def archive_history(self, versions, archive):
            assert archive is archive_store
            calls.append(("archive", versions))

        async def build_history(self, versions):
            calls.append(("build", versions))
            return resource

    class History:
        def __init__(self, **_kwargs) -> None:
            pass

        async def versions(self, current):
            assert current == "art-v2"
            calls.append(("history", current))
            return ("art-v1", "art-v2")

    monkeypatch.setattr(cli, "UpstreamArtBuilder", Builder)
    monkeypatch.setattr(cli, "WindowsVersionHistory", History)
    monkeypatch.setattr(cli, "_asset_bundle_archive", lambda _settings: archive_store)
    settings = SimpleNamespace(
        art_version_url="https://version.example",
        art_asset_base_url="https://assets.example",
        github_api_url="https://api.github.example",
        github_token=None,
        download_workers=2,
        extraction_workers=1,
    )

    update = await cli._prepare_art(settings, cache, complete=True, archive=True)
    manifest = await update.build(None, False)

    assert manifest is resource
    assert calls == [
        ("history", "art-v2"),
        ("archive", ("art-v1", "art-v2")),
        ("build", ("art-v1", "art-v2")),
    ]


@pytest.mark.asyncio
async def test_archive_preparation_failure_prevents_database_publication(monkeypatch, caplog):
    updater = _patch_runtime(monkeypatch)

    async def fail(_settings, _cache, *, complete=False, archive=False):
        assert complete is False
        assert archive is True
        raise RuntimeError("asset-bundle archive failed")

    monkeypatch.setattr(cli, "_prepare_art", fail)

    with caplog.at_level("ERROR"):
        result = await cli._run(["art"], force=False, archive=True, use_cache=False)

    assert result == 1
    assert updater.calls == []
    assert "unit=art status=failed" in caplog.text


@pytest.mark.asyncio
async def test_no_cache_workspace_outlives_batch_build_and_is_removed_after_run(monkeypatch):
    updater = _patch_runtime(monkeypatch)
    observed_root: Path | None = None

    async def prepare(_settings, cache: UpstreamCache):
        nonlocal observed_root
        observed_root = cache.root
        image_path = cache.root / "fixture.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (2, 3), (1, 2, 3, 255)).save(image_path, format="PNG")
        manifest = ArtManifest(
            "art-v1",
            (ArtRecord("fixture", "image", FilePngArtifact.from_path(image_path)),),
            (),
        )

        async def build(_active, _force):
            return manifest

        return UpdateRequest("art", "art-v1", build)

    async def run(requests, *, force=False):
        values = tuple(requests)
        updater.calls.append((values, force))
        manifest = await values[0].build(None, force)
        path = manifest.arts[0].image.path
        assert path is not None and path.is_file()
        return (UpdateResult("art", "art-v1", "updated"),)

    updater.run = run
    monkeypatch.setattr(cli, "_prepare_art", prepare)

    assert await cli._run(["art"], force=False, use_cache=False) == 0

    assert observed_root is not None
    assert not observed_root.exists()
