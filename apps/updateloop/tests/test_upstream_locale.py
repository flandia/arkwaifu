from __future__ import annotations

import asyncio
import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest

from arkwaifu_updateloop.domain import LocaleManifest
from arkwaifu_updateloop.upstream import UpstreamCache
from arkwaifu_updateloop.upstream.locale import LiveLocaleBuilder


def _archive(locales: dict[str, tuple[str, dict[str, object | str]]]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("ArknightsAssets-ArknightsGamedata-snapshot/.gitattributes", "")
        for server, (version, files) in locales.items():
            archive.writestr(
                f"ArknightsAssets-ArknightsGamedata-snapshot/{server}/hot_update_list.json",
                json.dumps({"versionId": version, "abInfos": []}),
            )
            for path, value in files.items():
                content = value if isinstance(value, str) else json.dumps(value)
                archive.writestr(
                    f"ArknightsAssets-ArknightsGamedata-snapshot/{server}/{path}",
                    content,
                )
    return output.getvalue()


def _empty_locale_files() -> dict[str, object | str]:
    return {
        "gamedata/excel/story_review_table.json": {},
        "gamedata/excel/story_review_meta_table.json": {
            "actArchiveResData": {"pics": {}},
            "actArchiveData": {"components": {}},
        },
        "gamedata/excel/activity_table.json": {},
        "gamedata/excel/replicate_table.json": {},
        "gamedata/excel/retro_table.json": {"retroActList": {}},
        "gamedata/excel/roguelike_topic_table.json": {"topics": {}},
        "gamedata/excel/stage_table.json": {},
    }


@pytest.mark.asyncio
async def test_locale_builder_uses_master_version_id_and_reuses_cached_archive(
    tmp_path, monkeypatch
):
    files = _empty_locale_files()
    files.update(
        {
            "gamedata/excel/story_review_table.json": {
                "group": {
                    "id": "group",
                    "name": "Main",
                    "actType": "MAIN_STORY",
                    "infoUnlockDatas": [
                        {
                            "storyId": "story",
                            "storyTxt": "opening",
                            "avgTag": "Before Operation",
                        }
                    ],
                }
            },
            "gamedata/excel/story_review_meta_table.json": {
                "actArchiveResData": {
                    "pics": {
                        "event": {
                            "id": "event",
                            "assetPath": "event",
                            "desc": "Event",
                        }
                    }
                },
                "actArchiveData": {"components": {}},
            },
            "gamedata/story/opening.txt": '[image(image="EVENT")] ',
        }
    )
    archive = _archive({"en": ("data-version", files)})
    zip_downloads = 0
    version_requests = 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal version_requests, zip_downloads
        path = request.url.path
        if path.endswith("/contents/en/hot_update_list.json"):
            version_requests += 1
            assert request.url.params["ref"] == "master"
            assert request.headers["accept"] == "application/vnd.github.raw+json"
            return httpx.Response(200, json={"versionId": "data-version", "abInfos": []})
        if path.endswith("/zipball/master"):
            zip_downloads += 1
            return httpx.Response(200, content=archive)
        return httpx.Response(404)

    def unexpected_validate(_manifest: LocaleManifest) -> None:
        raise AssertionError("locale adapter must not call manifest.validate")

    monkeypatch.setattr(LocaleManifest, "validate", unexpected_validate, raising=False)
    builder = LiveLocaleBuilder(
        transport=httpx.MockTransport(respond),
        cache=UpstreamCache(tmp_path / ".cache"),
    )

    version = await builder.detect_version("EN")
    manifest = await builder.build("EN", version, None, False)
    cached_manifest = await builder.build("EN", version, None, True)

    assert version == "data-version"
    assert version_requests == 1
    assert manifest.unit == "EN"
    assert manifest.upstream_version == "data-version"
    assert manifest.story_groups[0].stories[0].art_references[0].title == "Event"
    assert cached_manifest == manifest
    assert zip_downloads == 1
    assert (tmp_path / ".cache" / "game-data" / "archive.zip").is_file()
    assert (tmp_path / ".cache" / version / "game-data" / "EN" / "extracted").is_dir()
    assert not any("snapshot" in path.name for path in (tmp_path / ".cache").rglob("*"))
    await builder.aclose()


@pytest.mark.asyncio
async def test_one_run_scoped_locale_builder_caches_one_all_server_archive(tmp_path):
    archive = _archive(
        {
            "en": ("en-version", _empty_locale_files()),
            "jp": ("jp-version", _empty_locale_files()),
        }
    )
    zip_downloads = 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal zip_downloads
        if request.url.path.endswith("/contents/en/hot_update_list.json"):
            return httpx.Response(200, json={"versionId": "en-version"})
        if request.url.path.endswith("/contents/jp/hot_update_list.json"):
            return httpx.Response(200, json={"versionId": "jp-version"})
        if request.url.path.endswith("/zipball/master"):
            zip_downloads += 1
            return httpx.Response(200, content=archive)
        return httpx.Response(404)

    transport = httpx.MockTransport(respond)
    cache = UpstreamCache(tmp_path / ".cache")
    cached_archive = cache.root / "game-data" / "archive.zip"
    cached_archive.parent.mkdir(parents=True)
    cached_archive.write_bytes(
        _archive(
            {
                "en": ("en-version", _empty_locale_files()),
                "jp": ("stale-jp-version", _empty_locale_files()),
            }
        )
    )
    builder = LiveLocaleBuilder(transport=transport, cache=cache)
    en_version, jp_version = await asyncio.gather(
        builder.detect_version("EN"),
        builder.detect_version("JP"),
    )

    en, jp = await asyncio.gather(
        builder.build("EN", en_version, None, False),
        builder.build("JP", jp_version, None, False),
    )

    assert (en.unit, en.upstream_version) == ("EN", "en-version")
    assert (jp.unit, jp.upstream_version) == ("JP", "jp-version")
    assert zip_downloads == 1
    assert list(cache.root.rglob("archive.zip")) == [cached_archive]
    assert (cache.root / "en-version" / "game-data" / "EN" / "extracted").is_dir()
    assert (cache.root / "jp-version" / "game-data" / "JP" / "extracted").is_dir()
    await builder.aclose()


@pytest.mark.asyncio
async def test_locale_builder_recovers_missing_story_directory_from_history(tmp_path):
    files = _empty_locale_files()
    files.update(
        {
            "gamedata/excel/story_review_table.json": {
                "retired": {
                    "id": "retired",
                    "name": "Retired event",
                    "actType": "ACTIVITY_STORY",
                    "infoUnlockDatas": [
                        {
                            "storyId": "retired_opening",
                            "storyTxt": "activities/retired/opening",
                            "avgTag": "Before Operation",
                        },
                        {
                            "storyId": "retired_ending",
                            "storyTxt": "activities/retired/ending",
                            "avgTag": "After Operation",
                        },
                    ],
                }
            },
            "gamedata/excel/story_review_meta_table.json": {
                "actArchiveResData": {
                    "pics": {
                        "opening": {
                            "id": "opening",
                            "assetPath": "opening_art",
                            "desc": "Opening",
                        },
                        "ending": {
                            "id": "ending",
                            "assetPath": "ending_art",
                            "desc": "Ending",
                        },
                    }
                },
                "actArchiveData": {"components": {}},
            },
        }
    )
    archive = _archive({"en": ("data-version", files)})
    history_api_requests: list[str] = []
    raw_downloads: list[str] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/contents/en/hot_update_list.json"):
            return httpx.Response(200, json={"versionId": "data-version"})
        if path.endswith("/zipball/master"):
            return httpx.Response(200, content=archive)
        if path.endswith("/commits"):
            history_api_requests.append(str(request.url))
            assert request.url.params["sha"] == "master"
            assert request.url.params["path"] == "en/gamedata/story/activities/retired"
            assert request.url.params["per_page"] == "100"
            return httpx.Response(
                200,
                json=[
                    {
                        "sha": "delete-commit",
                        "parents": [{"sha": "before-delete"}],
                    }
                ],
            )
        if path.endswith("/contents/en/gamedata/story/activities/retired"):
            history_api_requests.append(str(request.url))
            assert request.url.params["ref"] == "before-delete"
            return httpx.Response(
                200,
                json=[
                    {"name": "opening.txt", "type": "file"},
                    {"name": "ending.txt", "type": "file"},
                ],
            )
        if request.url.host == "raw.githubusercontent.com":
            assert "authorization" not in request.headers
            raw_downloads.append(path)
            if path.endswith("/opening.txt"):
                return httpx.Response(200, text='[image(image="OPENING_ART")]')
            if path.endswith("/ending.txt"):
                return httpx.Response(200, text='[image(image="ENDING_ART")]')
        return httpx.Response(404)

    builder = LiveLocaleBuilder(
        github_token="private-token",
        transport=httpx.MockTransport(respond),
        cache=UpstreamCache(tmp_path / ".cache"),
    )
    version = await builder.detect_version("EN")

    manifest = await builder.build("EN", version, None, False)
    cached_manifest = await builder.build("EN", version, None, True)

    references = [
        reference.art_id
        for story in manifest.story_groups[0].stories
        for reference in story.art_references
    ]
    assert references == ["opening_art", "ending_art"]
    assert cached_manifest == manifest
    assert len(history_api_requests) == 2
    assert len(raw_downloads) == 2
    assert (
        tmp_path
        / ".cache"
        / version
        / "game-data"
        / "EN"
        / "extracted"
        / "assets"
        / "torappu"
        / "dynamicassets"
        / "gamedata"
        / "story"
        / "activities"
        / "retired"
        / "opening.txt"
    ).is_file()
    await builder.aclose()


@pytest.mark.asyncio
async def test_uncached_builder_releases_its_run_scoped_archive():
    archive = _archive({"en": ("en-version", _empty_locale_files())})

    async def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/contents/en/hot_update_list.json"):
            return httpx.Response(200, json={"versionId": "en-version"})
        if request.url.path.endswith("/zipball/master"):
            return httpx.Response(200, content=archive)
        return httpx.Response(404)

    builder = LiveLocaleBuilder(transport=httpx.MockTransport(respond))
    version = await builder.detect_version("EN")
    await builder.build("EN", version, None, False)
    archive_path = await builder._archive()
    archive_directory = archive_path.parent

    assert archive_path.is_file()
    await builder.aclose()
    assert not archive_directory.exists()
    with pytest.raises(RuntimeError, match="locale builder is closed"):
        await builder.detect_version("EN")


@pytest.mark.asyncio
async def test_version_detection_supports_tw():
    async def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/contents/tw/hot_update_list.json")
        assert request.url.params["ref"] == "master"
        return httpx.Response(200, json={"versionId": "tw-version"})

    builder = LiveLocaleBuilder(transport=httpx.MockTransport(respond))

    assert await builder.detect_version("TW") == "tw-version"


@pytest.mark.asyncio
async def test_version_detection_rejects_missing_version_id():
    async def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "wrong-field"})

    builder = LiveLocaleBuilder(transport=httpx.MockTransport(respond))

    with pytest.raises(TypeError, match="versionId"):
        await builder.detect_version("CN")


@pytest.mark.asyncio
async def test_build_rejects_master_snapshot_that_raced_detected_version():
    archive = _archive({"cn": ("version-2", _empty_locale_files())})
    version_requests = 0
    zip_downloads = 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal version_requests, zip_downloads
        if request.url.path.endswith("/contents/cn/hot_update_list.json"):
            version_requests += 1
            return httpx.Response(200, json={"versionId": "version-1"})
        if request.url.path.endswith("/zipball/master"):
            zip_downloads += 1
            return httpx.Response(200, content=archive)
        return httpx.Response(404)

    builder = LiveLocaleBuilder(transport=httpx.MockTransport(respond))
    detected = await builder.detect_version("CN")

    with pytest.raises(RuntimeError, match="changed from version-1 to version-2"):
        await builder.build("CN", detected, None, False)
    assert version_requests == 1
    assert zip_downloads == 1
    await builder.aclose()


def test_extract_rejects_parent_traversal(tmp_path):
    archive_path = tmp_path / "unsafe.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("../outside.json", "{}")

    with pytest.raises(ValueError, match="unsafe game-data archive member"):
        LiveLocaleBuilder._extract(archive_path, tmp_path / "output", "en")
