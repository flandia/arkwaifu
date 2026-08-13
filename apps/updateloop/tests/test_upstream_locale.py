from __future__ import annotations

import asyncio
import json
import subprocess
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import httpx
import pytest

from arkwaifu_updateloop.domain import LocaleManifest
from arkwaifu_updateloop.upstream import UpstreamCache
from arkwaifu_updateloop.upstream import locale as locale_upstream
from arkwaifu_updateloop.upstream.locale import UpstreamLocaleBuilder

_MISSING_STORY_PATH = "gamedata/story/activities/retired/opening.txt"


def _git(*arguments: str) -> bytes:
    return subprocess.run(
        ("git", *arguments),
        check=True,
        capture_output=True,
    ).stdout


def _commit_story_history(
    repository: Path,
    root: str,
    revisions: tuple[str, ...],
) -> None:
    story = repository / root / Path(_MISSING_STORY_PATH)
    relative_story = story.relative_to(repository).as_posix()
    for number, content in enumerate(revisions, start=1):
        story.parent.mkdir(parents=True, exist_ok=True)
        story.write_text(content, encoding="utf-8", newline="")
        _git("-C", str(repository), "add", "--force", "--", relative_story)
        _git(
            "-C",
            str(repository),
            "commit",
            "--quiet",
            "--message",
            f"story revision {number}",
        )
    if revisions:
        story.unlink()
        _git("-C", str(repository), "add", "--update", "--", relative_story)
        _git("-C", str(repository), "commit", "--quiet", "--message", "remove story")


def _history_repository(
    parent: Path,
    name: str,
    *,
    branch: str,
    root: str,
    revisions: tuple[str, ...],
) -> tuple[str, Path]:
    """Create a local history source whose optional story is deleted at HEAD."""

    repository = parent / name
    _git("init", "--quiet", "--initial-branch", branch, str(repository))
    for key, value in (
        ("user.name", "Arkwaifu tests"),
        ("user.email", "tests@example.invalid"),
        ("commit.gpgSign", "false"),
        ("core.autocrlf", "false"),
        ("core.hooksPath", ".git/no-hooks"),
        ("uploadpack.allowFilter", "true"),
    ):
        _git("-C", str(repository), "config", key, value)

    readme = repository / "README"
    readme.write_text("fixture\n", encoding="utf-8")
    _git("-C", str(repository), "add", "--force", "--", "README")
    _git("-C", str(repository), "commit", "--quiet", "--message", "initial")

    _commit_story_history(repository, root, revisions)
    return repository.resolve().as_uri(), repository


def test_story_history_sources_follow_the_locale_recovery_priority() -> None:
    sources = tuple(
        (
            unit,
            url.removeprefix("https://github.com/").removesuffix(".git"),
            branch,
            root,
        )
        for unit, unit_sources in locale_upstream._STORY_HISTORY_SOURCES.items()
        for url, branch, root in unit_sources
    )

    assert sources == (
        ("CN", "ArknightsAssets/ArknightsGamedata", "master", "cn"),
        ("CN", "Kengxxiao/ArknightsGameData", "master", "zh_CN"),
        ("EN", "ArknightsAssets/ArknightsGamedata", "master", "en"),
        ("EN", "Kengxxiao/ArknightsGameData_YoStar", "main", "en_US"),
        ("EN", "Kengxxiao/ArknightsGameData", "master", "en_US"),
        ("JP", "ArknightsAssets/ArknightsGamedata", "master", "jp"),
        ("JP", "Kengxxiao/ArknightsGameData_YoStar", "main", "ja_JP"),
        ("JP", "Kengxxiao/ArknightsGameData", "master", "ja_JP"),
        ("KR", "ArknightsAssets/ArknightsGamedata", "master", "kr"),
        ("KR", "Kengxxiao/ArknightsGameData_YoStar", "main", "ko_KR"),
        ("KR", "Kengxxiao/ArknightsGameData", "master", "ko_KR"),
        ("TW", "ArknightsAssets/ArknightsGamedata", "master", "tw"),
        ("TW", "aelurum/ArknightsGameData", "master_v2", "zh_TW"),
    )


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
        "gamedata/excel/sandbox_perm_table.json": {"basicInfo": {}, "detail": {}},
        "gamedata/excel/stage_table.json": {},
    }


def _missing_story_files() -> dict[str, object | str]:
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
                        }
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
                        }
                    }
                },
                "actArchiveData": {"components": {}},
            },
        }
    )
    return files


def test_missing_story_paths_include_official_endings_and_reclamation_stories(
    tmp_path: Path,
):
    excel = tmp_path / "assets/torappu/dynamicassets/gamedata/excel"
    excel.mkdir(parents=True)
    (excel / "story_review_table.json").write_text(
        json.dumps(
            {
                "group": {
                    "infoUnlockDatas": [
                        {"storyTxt": "activities/missing"},
                        {"storyTxt": "activities/present"},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    (excel / "roguelike_topic_table.json").write_text(
        json.dumps(
            {
                "details": {
                    "rogue": {
                        "archiveComp": {
                            "chat": {
                                "chat": {
                                    "monthly": {
                                        "chatItemList": [
                                            {"chatStoryId": "Obt/Rogue/monthly_missing"}
                                        ]
                                    }
                                }
                            },
                            "endbook": {
                                "endbook": {"ending": {"avgId": "Obt/Roguelike/RO2/ending_missing"}}
                            },
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (excel / "story_review_meta_table.json").write_text(
        json.dumps(
            {
                "actArchiveResData": {
                    "avgs": {
                        "opening": {"contentPath": "Obt/Roguelike/RO1/level_rogue1_entry"},
                        "ending": {"contentPath": ("Obt/Roguelike/RO1/level_rogue1_ending_1")},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (excel / "sandbox_perm_table.json").write_text(
        json.dumps(
            {
                "detail": {
                    "SANDBOX": {
                        "sandbox": {
                            "archiveQuestData": {
                                "quest": {
                                    "avgDataList": [
                                        {"avgId": ("Obt/SandboxPerm/sandbox/ending_missing")}
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    present = tmp_path / "assets/torappu/dynamicassets/gamedata/story/activities/present.txt"
    present.parent.mkdir(parents=True)
    present.write_text("present", encoding="utf-8")

    assert locale_upstream._missing_story_paths(tmp_path) == (
        PurePosixPath("gamedata/story/activities/missing.txt"),
        PurePosixPath("gamedata/story/obt/roguelike/ro2/ending_missing.txt"),
        PurePosixPath("gamedata/story/obt/sandboxperm/sandbox/ending_missing.txt"),
        PurePosixPath("gamedata/story/obt/roguelike/ro1/level_rogue1_ending_1.txt"),
    )


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
    builder = UpstreamLocaleBuilder(
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
async def test_locale_builder_reextracts_a_corrupt_cached_locale(tmp_path: Path):
    archive = _archive({"en": ("data-version", _empty_locale_files())})
    archive_downloads = 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal archive_downloads
        if request.url.path.endswith("/zipball/master"):
            archive_downloads += 1
            return httpx.Response(200, content=archive)
        raise AssertionError(f"unexpected request: {request.url}")

    cache = UpstreamCache(tmp_path / ".cache")
    builder = UpstreamLocaleBuilder(
        transport=httpx.MockTransport(respond),
        cache=cache,
    )
    first = await builder.build("EN", "data-version", None, False)
    cached_table = (
        cache.root
        / "data-version/game-data/EN/extracted"
        / "assets/torappu/dynamicassets/gamedata/excel/story_review_table.json"
    )
    cached_table.write_text("{", encoding="utf-8")

    rebuilt = await builder.build("EN", "data-version", None, False)

    assert rebuilt == first
    assert json.loads(cached_table.read_text(encoding="utf-8")) == {}
    assert archive_downloads == 1
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
    builder = UpstreamLocaleBuilder(transport=transport, cache=cache)
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
async def test_locale_builder_recovers_latest_existing_story_and_caches_it(
    tmp_path,
    monkeypatch,
):
    repository_url, repository = _history_repository(
        tmp_path,
        "primary-history",
        branch="main",
        root="en",
        revisions=(
            '[image(image="STALE_ART")]',
            '[image(image="OPENING_ART")]',
        ),
    )
    monkeypatch.setattr(
        "arkwaifu_updateloop.upstream.locale._STORY_HISTORY_SOURCES",
        {"EN": ((repository_url, "main", "en"),)},
    )
    archive = _archive({"en": ("data-version", _missing_story_files())})
    archive_downloads = 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal archive_downloads
        if request.url.path.endswith("/zipball/master"):
            archive_downloads += 1
            return httpx.Response(200, content=archive)
        raise AssertionError(f"unexpected request: {request.url}")

    cache = UpstreamCache(tmp_path / ".cache")
    builder = UpstreamLocaleBuilder(
        transport=httpx.MockTransport(respond),
        cache=cache,
    )
    manifest = await builder.build("EN", "data-version", None, False)
    history_directory = Path(builder._history_directory.name)

    assert [
        reference.art_id
        for story in manifest.story_groups[0].stories
        for reference in story.art_references
    ] == ["opening_art"]
    assert history_directory.is_dir()
    await builder.aclose()
    assert not history_directory.exists()

    repository.rename(tmp_path / "history-now-unavailable")
    cached_builder = UpstreamLocaleBuilder(
        transport=httpx.MockTransport(respond),
        cache=cache,
    )
    cached_manifest = await cached_builder.build("EN", "data-version", None, False)

    assert cached_manifest == manifest
    assert archive_downloads == 1
    assert cached_builder._history_directory is None
    await cached_builder.aclose()


@pytest.mark.asyncio
async def test_locale_builder_uses_the_first_history_source_containing_the_story(
    tmp_path,
    monkeypatch,
):
    primary_url, _ = _history_repository(
        tmp_path,
        "primary-history",
        branch="master",
        root="en",
        revisions=(),
    )
    fallback_url, _ = _history_repository(
        tmp_path,
        "yostar-history",
        branch="main",
        root="en_US",
        revisions=('[image(image="YOSTAR_ART")]',),
    )
    later_url, _ = _history_repository(
        tmp_path,
        "older-history",
        branch="master",
        root="en_US",
        revisions=('[image(image="OLDER_ART")]',),
    )
    monkeypatch.setattr(
        "arkwaifu_updateloop.upstream.locale._STORY_HISTORY_SOURCES",
        {
            "EN": (
                (primary_url, "master", "en"),
                (fallback_url, "main", "en_US"),
                (later_url, "master", "en_US"),
            )
        },
    )
    archive = _archive({"en": ("data-version", _missing_story_files())})

    async def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/zipball/master"):
            return httpx.Response(200, content=archive)
        raise AssertionError(f"unexpected request: {request.url}")

    builder = UpstreamLocaleBuilder(transport=httpx.MockTransport(respond))
    manifest = await builder.build("EN", "data-version", None, False)

    assert [
        reference.art_id
        for story in manifest.story_groups[0].stories
        for reference in story.art_references
    ] == ["yostar_art"]
    assert len(builder._history_clone_tasks) == 2
    assert (later_url, "master") not in builder._history_clone_tasks
    await builder.aclose()


@pytest.mark.asyncio
async def test_concurrent_locales_share_one_history_clone(tmp_path, monkeypatch):
    repository_url, repository = _history_repository(
        tmp_path,
        "shared-history",
        branch="main",
        root="en",
        revisions=('[image(image="EN_ART")]',),
    )
    _commit_story_history(
        repository,
        "ja_JP",
        ('[image(image="JP_ART")]',),
    )
    monkeypatch.setattr(
        locale_upstream,
        "_STORY_HISTORY_SOURCES",
        {
            "EN": ((repository_url, "main", "en"),),
            "JP": ((repository_url, "main", "ja_JP"),),
        },
    )
    clone_calls = 0
    clone_repository = UpstreamLocaleBuilder._clone_history_repository

    async def counted_clone(self, repository_url, branch, destination):
        nonlocal clone_calls
        clone_calls += 1
        return await clone_repository(self, repository_url, branch, destination)

    monkeypatch.setattr(UpstreamLocaleBuilder, "_clone_history_repository", counted_clone)
    archive = _archive(
        {
            "en": ("en-version", _missing_story_files()),
            "jp": ("jp-version", _missing_story_files()),
        }
    )

    async def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/zipball/master"):
            return httpx.Response(200, content=archive)
        raise AssertionError(f"unexpected request: {request.url}")

    builder = UpstreamLocaleBuilder(transport=httpx.MockTransport(respond))
    try:
        en, jp = await asyncio.gather(
            builder.build("EN", "en-version", None, False),
            builder.build("JP", "jp-version", None, False),
        )

        def art_ids(manifest: LocaleManifest) -> list[str]:
            return [
                reference.art_id
                for story in manifest.story_groups[0].stories
                for reference in story.art_references
            ]

        assert (art_ids(en), art_ids(jp)) == (["en_art"], ["jp_art"])
        assert clone_calls == 1
        assert len(builder._history_clone_tasks) == 1
    finally:
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

    builder = UpstreamLocaleBuilder(transport=httpx.MockTransport(respond))
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

    builder = UpstreamLocaleBuilder(transport=httpx.MockTransport(respond))

    assert await builder.detect_version("TW") == "tw-version"


@pytest.mark.asyncio
async def test_version_detection_rejects_missing_version_id():
    async def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "wrong-field"})

    builder = UpstreamLocaleBuilder(transport=httpx.MockTransport(respond))

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

    builder = UpstreamLocaleBuilder(transport=httpx.MockTransport(respond))
    detected = await builder.detect_version("CN")

    with pytest.raises(RuntimeError, match="changed from version-1 to version-2"):
        await builder.build("CN", detected, None, False)
    assert version_requests == 1
    assert zip_downloads == 1
    await builder.aclose()


@pytest.mark.parametrize(
    "member",
    [
        "../outside.json",
        "snapshot/en/gamedata/story/../outside.txt",
        "snapshot/en/gamedata/story/C:/outside.txt",
        "snapshot/en/gamedata/story/\\outside.txt",
    ],
)
def test_extract_rejects_unsafe_local_paths(tmp_path: Path, member: str):
    archive_path = tmp_path / "unsafe.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        info = ZipInfo()
        info.filename = member
        info.orig_filename = member
        info.compress_type = ZIP_DEFLATED
        archive.writestr(info, "outside")

    with pytest.raises(ValueError, match="unsafe game-data archive member"):
        UpstreamLocaleBuilder._extract(archive_path, tmp_path / "output", "en")


@pytest.mark.parametrize(
    "path",
    [
        PurePosixPath("../outside.txt"),
        PurePosixPath("/outside.txt"),
        PurePosixPath("C:/outside.txt"),
        PurePosixPath("gamedata/story/\\outside.txt"),
    ],
)
def test_historical_recovery_rejects_unsafe_local_paths(tmp_path: Path, path: PurePosixPath):
    with pytest.raises(ValueError, match="unsafe historical story path"):
        locale_upstream._write_story_text(tmp_path, path, b"outside")
