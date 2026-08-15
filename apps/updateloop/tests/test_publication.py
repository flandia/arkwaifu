from __future__ import annotations

import asyncio
import sqlite3
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from arkwaifu_updateloop import (
    DATABASE_OBJECT_KEY,
    MemoryObjectStore,
    S3ObjectStore,
    Updater,
    UpdateRequest,
    UpdateResult,
)
from arkwaifu_updateloop import object_store as remote_module
from arkwaifu_updateloop import updater as updater_module
from arkwaifu_updateloop.database import initialize_or_validate
from arkwaifu_updateloop.domain import (
    ArchiveGroup,
    ArtManifest,
    ArtRecord,
    FilePngArtifact,
    FileVideoArtifact,
    GalleryArtwork,
    GalleryDisplay,
    GalleryGroup,
    LocaleManifest,
    Movement,
    MovementLocation,
    MovementSection,
    PngArtifact,
    ScoreAssetRecord,
    ScoreVideoRecord,
    SourceArtRecord,
    SourceArtReference,
    StoryArtReference,
    StoryRecord,
)
from arkwaifu_updateloop.thumbnail import make_thumbnail
from arkwaifu_updateloop.updater import (
    art_object_key,
    score_asset_object_key,
    score_video_object_key,
)


def art_manifest(
    version: str,
    art_id: str,
    color: tuple[int, int, int, int] = (1, 2, 3, 255),
    *,
    category: str = "image",
) -> ArtManifest:
    return ArtManifest(
        upstream_version=version,
        arts=(
            ArtRecord(
                id=art_id,
                category=category,
                image=PngArtifact.from_image(Image.new("RGBA", (2, 2), color)),
            ),
        ),
        source_arts=(),
    )


def character_manifest(version: str, character_id: str) -> ArtManifest:
    source_id = f"{character_id}:body:1"
    source = SourceArtRecord(
        id=source_id,
        category="character",
        kind="character",
        character_id=character_id,
        role="body",
        variant="1",
        image=PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255))),
    )
    art = ArtRecord(
        id=f"{character_id}#1$1",
        category="character",
        image=PngArtifact.from_image(Image.new("RGBA", (2, 3), (3, 2, 1, 255))),
        source_art_references=(SourceArtReference("character", source_id),),
    )
    return ArtManifest(version, (art,), (source,))


def locale_manifest(
    unit: str,
    version: str,
    *,
    suffix: str = "one",
    art_id: str = "event",
) -> LocaleManifest:
    movement_id = f"movement_{suffix}"
    section_id = f"section_{suffix}"
    section_collection_id = f"movement_section:{section_id}"
    group_id = f"group_{suffix}"
    group_collection_id = f"archive_group:{group_id}"
    story_id = f"story_{suffix}"
    gallery_id = f"gallery_{suffix}"
    return LocaleManifest(
        unit=unit,
        upstream_version=version,
        movements=(
            Movement(
                id=movement_id,
                position=0,
                movement_type="continue",
                name="Movement",
                icon_asset_id=None,
                logo_asset_id=None,
                background_asset_id=None,
                has_video=False,
                start_time=0,
                locations=(
                    MovementLocation(
                        id=f"story_set_{suffix}",
                        position=0,
                        location_type="story_set",
                        sort_id=0,
                        start_time=0,
                        present_stage_id=None,
                        unlock_stage_id=None,
                        section_id=section_id,
                        split_icon_asset_id=None,
                        split_sub_name=None,
                        video_id=None,
                    ),
                ),
            ),
        ),
        movement_sections=(
            MovementSection(
                id=section_id,
                collection_id=section_collection_id,
                section_type="main_theme",
                name="Section",
                review_group_id=None,
                sort_by_year=0,
                sort_within_year=0,
                key_visual_asset_id=None,
                title_asset_id=None,
                background_asset_id=None,
                decoration_asset_id=None,
                retro_background_asset_id=None,
                description="",
                has_video=False,
                stories=(),
            ),
        ),
        archive_groups=(
            ArchiveGroup(
                id=group_id,
                collection_id=group_collection_id,
                position=0,
                name="Group",
                archive_kind="events",
                story_type="side_story",
                stories=(
                    StoryRecord(
                        id=story_id,
                        collection_id=group_collection_id,
                        tag="before",
                        tag_text="Before Operation",
                        code="1",
                        name="Story",
                        info="",
                        art_references=(
                            StoryArtReference(
                                art_id,
                                "picture",
                                "image",
                                "Title",
                                "Subtitle",
                                ("A", "B"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        galleries=(
            GalleryGroup(
                id=gallery_id,
                collection_id=group_collection_id,
                position=0,
                name="Gallery",
                description="Description",
                location_id=None,
                displays=(
                    GalleryDisplay(
                        id=f"display_{suffix}",
                        position=0,
                        name="Entry",
                        description="",
                        related_story_id=story_id,
                        related_stage_id=None,
                        artworks=(
                            GalleryArtwork(
                                position=0,
                                cg_id=f"entry_{suffix}",
                                art_id=art_id,
                                category="image",
                                composite_type="none",
                                panels=(),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def update_request(manifest: ArtManifest | LocaleManifest) -> UpdateRequest:
    async def build(_active: str | None, _force: bool):
        return manifest

    if isinstance(manifest, ArtManifest):
        return UpdateRequest("art", manifest.upstream_version, build)
    return UpdateRequest(manifest.unit, manifest.upstream_version, build)


def database_connection(remote: MemoryObjectStore, tmp_path: Path) -> sqlite3.Connection:
    assert remote.database is not None
    path = tmp_path / "arkwaifu.sqlite3"
    path.write_bytes(remote.database)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def video_artifact(tmp_path: Path, content: bytes = b"webm-fixture") -> FileVideoArtifact:
    path = tmp_path / "score.webm"
    path.write_bytes(content)
    return FileVideoArtifact.from_path(
        path,
        width=1920,
        height=1080,
        frame_rate_numerator=30,
        frame_rate_denominator=1,
        frame_count=60,
    )


def test_object_key_uses_requested_art_path_and_logical_identity_without_sha():
    key = art_object_key(
        res_version="v1",
        variant="composition",
        category="character",
        identifier="char#1$2",
    )

    assert key == "ART/v1/composition/character/char%231%242.png"


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("source", "ART/v1/source/character/id.png"),
        ("composition", "ART/v1/composition/character/id.png"),
    ],
)
def test_object_key_supports_art_variants(variant, expected):
    assert (
        art_object_key(
            res_version="v1",
            variant=variant,
            category="character",
            identifier="id",
        )
        == expected
    )


@pytest.mark.parametrize(
    "kind",
    [
        "icon",
        "logo",
        "background",
        "key_visual",
        "title",
        "decoration",
        "retro_background",
        "split",
    ],
)
def test_score_asset_object_key_has_a_deep_kind_namespace(kind):
    assert (
        score_asset_object_key(
            res_version="v 1",
            kind=kind,
            identifier="asset/id",
        )
        == f"SCORE/v%201/{kind}/asset%2Fid.png"
    )


@pytest.mark.parametrize("kind", ["", "video", "unknown"])
def test_score_asset_object_key_rejects_unknown_kinds(kind):
    with pytest.raises(ValueError, match="unknown Score asset kind"):
        score_asset_object_key(res_version="v1", kind=kind, identifier="asset")


def test_score_video_object_key_has_a_dedicated_namespace():
    assert (
        score_video_object_key(
            res_version="v 1",
            identifier="background/id",
        )
        == "SCORE/v%201/video/background%2Fid.webm"
    )


def test_database_object_is_named_arkwaifu():
    assert DATABASE_OBJECT_KEY == "arkwaifu.sqlite3"


async def test_s3_remote_streams_a_file_backed_png(monkeypatch, tmp_path):
    class Client:
        def __init__(self) -> None:
            self.puts = []

        def head_object(self, **_kwargs):
            raise remote_module.ClientError(
                {"Error": {"Code": "404"}},
                "HeadObject",
            )

        def put_object(self, **kwargs):
            kwargs = dict(kwargs)
            kwargs["Body"] = kwargs["Body"].read()
            self.puts.append(kwargs)

    client = Client()
    monkeypatch.setattr(remote_module.boto3, "client", lambda *_args, **_kwargs: client)
    png_path = tmp_path / "art.png"
    Image.new("RGBA", (2, 3), (1, 2, 3, 255)).save(png_path, format="PNG")
    artifact = FilePngArtifact.from_path(png_path)
    remote = S3ObjectStore(
        bucket="bucket",
        region="region",
        access_key_id="access",
        secret_access_key="secret",
    )

    await remote.put_png("ART/v1/composition/image/art.png", artifact)

    assert client.puts == [
        {
            "Bucket": "bucket",
            "Key": "ART/v1/composition/image/art.png",
            "Body": png_path.read_bytes(),
            "ContentLength": artifact.byte_size,
            "ContentType": "image/png",
            "CacheControl": "public, max-age=31536000, immutable",
        }
    ]


async def test_s3_remote_accepts_matching_immutable_png_without_put(monkeypatch):
    artifact = PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255)))

    class Client:
        def head_object(self, **_kwargs):
            return {
                "ContentLength": artifact.byte_size,
                "ContentType": "image/png",
                "CacheControl": "public, max-age=31536000, immutable",
            }

        def put_object(self, **_kwargs):
            raise AssertionError("matching immutable PNG must not be replaced")

    monkeypatch.setattr(remote_module.boto3, "client", lambda *_args, **_kwargs: Client())
    remote = S3ObjectStore(
        bucket="bucket",
        region="region",
        access_key_id="access",
        secret_access_key="secret",
    )

    await remote.put_png("ART/v1/composition/image/art.png", artifact)


async def test_s3_remote_rejects_conflicting_immutable_png(monkeypatch):
    artifact = PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255)))

    class Client:
        def head_object(self, **_kwargs):
            return {
                "ContentLength": artifact.byte_size + 1,
                "ContentType": "image/png",
                "CacheControl": "public, max-age=31536000, immutable",
            }

    monkeypatch.setattr(remote_module.boto3, "client", lambda *_args, **_kwargs: Client())
    remote = S3ObjectStore(
        bucket="bucket",
        region="region",
        access_key_id="access",
        secret_access_key="secret",
    )

    with pytest.raises(ValueError, match="immutable PNG object conflicts"):
        await remote.put_png("ART/v1/composition/image/art.png", artifact)


async def test_s3_remote_streams_a_file_backed_score_video(monkeypatch, tmp_path):
    class Client:
        def __init__(self) -> None:
            self.puts = []

        def head_object(self, **_kwargs):
            raise remote_module.ClientError(
                {"Error": {"Code": "404"}},
                "HeadObject",
            )

        def put_object(self, **kwargs):
            kwargs = dict(kwargs)
            kwargs["Body"] = kwargs["Body"].read()
            self.puts.append(kwargs)

    client = Client()
    monkeypatch.setattr(remote_module.boto3, "client", lambda *_args, **_kwargs: client)
    artifact = video_artifact(tmp_path)
    remote = S3ObjectStore(
        bucket="bucket",
        region="region",
        access_key_id="access",
        secret_access_key="secret",
    )

    await remote.put_video("SCORE/v1/video/background.webm", artifact)

    assert client.puts == [
        {
            "Bucket": "bucket",
            "Key": "SCORE/v1/video/background.webm",
            "Body": artifact.content,
            "ContentLength": artifact.byte_size,
            "ContentType": "video/webm",
            "CacheControl": "public, max-age=31536000, immutable",
        }
    ]


async def test_s3_remote_accepts_matching_immutable_score_video_without_put(
    monkeypatch,
    tmp_path,
):
    artifact = video_artifact(tmp_path)

    class Client:
        def head_object(self, **_kwargs):
            return {
                "ContentLength": artifact.byte_size,
                "ContentType": "video/webm",
                "CacheControl": "public, max-age=31536000, immutable",
            }

        def put_object(self, **_kwargs):
            raise AssertionError("matching immutable WebM must not be replaced")

    monkeypatch.setattr(remote_module.boto3, "client", lambda *_args, **_kwargs: Client())
    remote = S3ObjectStore(
        bucket="bucket",
        region="region",
        access_key_id="access",
        secret_access_key="secret",
    )

    await remote.put_video("SCORE/v1/video/background.webm", artifact)


async def test_s3_remote_rejects_conflicting_immutable_score_video(monkeypatch, tmp_path):
    artifact = video_artifact(tmp_path)

    class Client:
        def head_object(self, **_kwargs):
            return {
                "ContentLength": artifact.byte_size + 1,
                "ContentType": "video/webm",
                "CacheControl": "public, max-age=31536000, immutable",
            }

    monkeypatch.setattr(remote_module.boto3, "client", lambda *_args, **_kwargs: Client())
    remote = S3ObjectStore(
        bucket="bucket",
        region="region",
        access_key_id="access",
        secret_access_key="secret",
    )

    with pytest.raises(ValueError, match="immutable WebM object conflicts"):
        await remote.put_video("SCORE/v1/video/background.webm", artifact)


async def test_s3_remote_always_replaces_thumbnail_with_storage_defaults(monkeypatch):
    first = make_thumbnail(PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255))))
    second = make_thumbnail(PngArtifact.from_image(Image.new("RGBA", (2, 3), (4, 5, 6, 255))))

    class Client:
        def __init__(self) -> None:
            self.puts = []

        def head_object(self, **_kwargs):
            raise AssertionError("mutable thumbnails must not be inspected before replacement")

        def put_object(self, **kwargs):
            self.puts.append(kwargs)

    client = Client()
    monkeypatch.setattr(remote_module.boto3, "client", lambda *_args, **_kwargs: client)
    remote = S3ObjectStore(
        bucket="bucket",
        region="region",
        access_key_id="access",
        secret_access_key="secret",
    )
    key = "ART/v1/thumbnail/image/art.webp"

    await remote.put_thumbnail(key, first)
    await remote.put_thumbnail(key, second)

    assert [put["Body"] for put in client.puts] == [first, second]
    assert all(put["ContentType"] == "image/webp" for put in client.puts)
    assert all("CacheControl" not in put for put in client.puts)
    assert all("Metadata" not in put for put in client.puts)
    assert [put["ContentLength"] for put in client.puts] == [
        len(first),
        len(second),
    ]


async def test_memory_remote_replaces_mutable_thumbnail():
    remote = MemoryObjectStore()
    key = "ART/v1/thumbnail/image/art.webp"
    first = make_thumbnail(PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255))))
    second = make_thumbnail(PngArtifact.from_image(Image.new("RGBA", (2, 3), (4, 5, 6, 255))))

    await remote.put_thumbnail(key, first)
    await remote.put_thumbnail(key, second)

    assert remote.objects[key] == second


async def test_memory_remote_does_not_replace_versioned_png():
    remote = MemoryObjectStore()
    key = "ART/v1/composition/image/art.png"
    first = PngArtifact.from_image(Image.new("RGBA", (1, 1), (1, 2, 3, 255)))
    second = PngArtifact.from_image(Image.new("RGBA", (1, 1), (4, 5, 6, 255)))

    await remote.put_png(key, first)
    await remote.put_png(key, first)
    with pytest.raises(ValueError, match="immutable PNG object conflicts"):
        await remote.put_png(key, second)

    assert remote.objects[key] == first.content


async def test_memory_remote_does_not_replace_versioned_score_video(tmp_path):
    remote = MemoryObjectStore()
    key = "SCORE/v1/video/background.webm"
    first = video_artifact(tmp_path, b"first-video")
    second_path = tmp_path / "second.webm"
    second_path.write_bytes(b"second-video")
    second = FileVideoArtifact.from_path(
        second_path,
        width=1920,
        height=1080,
        frame_rate_numerator=30,
        frame_rate_denominator=1,
        frame_count=60,
    )

    await remote.put_video(key, first)
    await remote.put_video(key, first)
    with pytest.raises(ValueError, match="immutable WebM object conflicts"):
        await remote.put_video(key, second)

    assert remote.objects[key] == first.content


async def test_partial_first_run_creates_one_valid_database(tmp_path, caplog):
    remote = MemoryObjectStore()
    updater = Updater(remote)
    locale = locale_manifest("EN", "en-v1", art_id="absent")

    with caplog.at_level("WARNING", logger="arkwaifu_updateloop.incomplete_upstream"):
        result = await updater.run([update_request(locale)])

    assert result[0].status == "updated"
    assert "count=1" in caplog.text
    with database_connection(remote, tmp_path) as connection:
        assert dict(connection.execute("SELECT * FROM unit_versions").fetchone()) == {
            "unit": "EN",
            "res_version": "en-v1",
        }
        assert connection.execute("SELECT names_json FROM story_art_references").fetchone()[0] == (
            '["A","B"]'
        )


async def test_art_reference_requires_matching_category_and_id(caplog):
    remote = MemoryObjectStore()

    with caplog.at_level("WARNING", logger="arkwaifu_updateloop.incomplete_upstream"):
        await Updater(remote).run(
            [
                update_request(art_manifest("art-v1", "shared", category="background")),
                update_request(locale_manifest("EN", "en-v1", art_id="shared")),
            ]
        )

    assert "count=1" in caplog.text
    assert "image/shared" in caplog.text


async def test_locale_leading_missing_score_assets_warn_and_still_publish(caplog):
    remote = MemoryObjectStore()
    locale = locale_manifest("EN", "en-v1")
    movement = replace(
        locale.movements[0],
        icon_asset_id="missing-icon",
        locations=(replace(locale.movements[0].locations[0], video_id="missing-video"),),
    )
    section = replace(
        locale.movement_sections[0],
        key_visual_asset_id="missing-key-visual",
    )
    locale = replace(
        locale,
        movements=(movement,),
        movement_sections=(section,),
    )

    with caplog.at_level("WARNING", logger="arkwaifu_updateloop.incomplete_upstream"):
        result = await Updater(remote).run([update_request(locale)])

    assert result == (UpdateResult("EN", "en-v1", "updated"),)
    assert "database references unavailable Score assets" in caplog.text
    assert "count=3" in caplog.text
    assert "score/icon/missing-icon" in caplog.text
    assert "score/key_visual/missing-key-visual" in caplog.text
    assert "score/video/missing-video" in caplog.text


async def test_score_assets_and_videos_publish_before_database(tmp_path):
    remote = MemoryObjectStore()
    image = PngArtifact.from_image(Image.new("RGBA", (64, 32), (1, 2, 3, 255)))
    video = video_artifact(tmp_path)
    manifest = ArtManifest(
        upstream_version="art-v1",
        arts=(),
        source_arts=(),
        score_assets=(ScoreAssetRecord("icon-main", "icon", image),),
        score_videos=(ScoreVideoRecord("background-main", video),),
    )

    result = await Updater(remote).run([update_request(manifest)])

    assert result == (UpdateResult("art", "art-v1", "updated"),)
    assert remote.objects == {
        "SCORE/art-v1/icon/icon-main.png": image.content,
        "SCORE/art-v1/video/background-main.webm": video.content,
    }
    with database_connection(remote, tmp_path) as connection:
        assert tuple(
            connection.execute(
                "SELECT asset_kind, asset_id, object_key, byte_size, width, height "
                "FROM score_assets"
            ).fetchone()
        ) == (
            "icon",
            "icon-main",
            "SCORE/art-v1/icon/icon-main.png",
            image.byte_size,
            64,
            32,
        )
        assert tuple(
            connection.execute(
                "SELECT video_id, object_key, byte_size, width, height, "
                "frame_rate_numerator, frame_rate_denominator, frame_count "
                "FROM score_videos"
            ).fetchone()
        ) == (
            "background-main",
            "SCORE/art-v1/video/background-main.webm",
            video.byte_size,
            1920,
            1080,
            30,
            1,
            60,
        )


async def test_score_video_upload_failure_prevents_database_publication(tmp_path):
    class FailingRemote(MemoryObjectStore):
        async def put_video(self, _key, _artifact):
            raise RuntimeError("Score video upload failed")

    remote = FailingRemote()
    video = video_artifact(tmp_path)
    manifest = ArtManifest(
        upstream_version="art-v1",
        arts=(),
        source_arts=(),
        score_videos=(ScoreVideoRecord("background-main", video),),
    )

    with pytest.raises(RuntimeError, match="Score video upload failed"):
        await Updater(remote).run([update_request(manifest)])

    assert remote.database is None


@pytest.mark.parametrize(
    ("missing_fields", "missing"),
    [
        (("movements",), "movements"),
        (("galleries",), "galleries"),
        (("movements", "movement_sections"), "movements,movement_sections"),
        (("archive_groups", "galleries"), "archive_groups,galleries"),
    ],
)
async def test_incomplete_locale_sections_warn_and_still_publish(
    tmp_path,
    caplog,
    missing_fields,
    missing,
):
    remote = MemoryObjectStore()
    locale = locale_manifest("EN", "en-v1")
    locale = replace(locale, **{field: () for field in missing_fields})

    with caplog.at_level("WARNING", logger="arkwaifu_updateloop.incomplete_upstream"):
        results = await Updater(remote).run(
            [update_request(art_manifest("art-v1", "event")), update_request(locale)]
        )

    assert [result.status for result in results] == ["updated", "updated"]
    assert f"unit=EN res_version=en-v1 missing={missing}" in caplog.text
    with database_connection(remote, tmp_path) as connection:
        assert (
            connection.execute(
                "SELECT res_version FROM unit_versions WHERE unit = 'EN'"
            ).fetchone()[0]
            == "en-v1"
        )
        expected = {
            "movements": 0 if "movements" in missing_fields else 1,
            "movement_sections": 0 if "movement_sections" in missing_fields else 1,
            "archive_groups": 0 if "archive_groups" in missing_fields else 1,
            "gallery_groups": 0 if "galleries" in missing_fields else 1,
        }
        for table, count in expected.items():
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == count


async def test_equal_res_version_is_a_noop_without_calling_builder():
    remote = MemoryObjectStore()
    updater = Updater(remote)
    first = art_manifest("v1", "first")
    await updater.run([update_request(first)])
    original = remote.database
    called = False

    async def should_not_build(_active: str | None, _force: bool):
        nonlocal called
        called = True
        return first

    result = await updater.run([UpdateRequest("art", "v1", should_not_build)])

    assert result[0].status == "unchanged"
    assert called is False
    assert remote.database == original


async def test_missing_performance_index_is_published_without_rebuilding(tmp_path):
    class CountingRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.pushes = 0

        async def push_database(self, source):
            self.pushes += 1
            await super().push_database(source)

    legacy_path = tmp_path / "legacy.sqlite3"
    initialize_or_validate(legacy_path)
    connection = sqlite3.connect(legacy_path)
    try:
        connection.execute("INSERT INTO unit_versions VALUES ('art', 'v1')")
        connection.execute("DROP INDEX story_art_references_by_art")
        connection.commit()
    finally:
        connection.close()

    remote = CountingRemote()
    remote.database = legacy_path.read_bytes()
    called = False

    async def should_not_build(_active: str | None, _force: bool):
        nonlocal called
        called = True
        return art_manifest("v1", "unused")

    result = await Updater(remote).run([UpdateRequest("art", "v1", should_not_build)])

    assert result == (UpdateResult("art", "v1", "unchanged"),)
    assert called is False
    assert remote.pushes == 1
    with database_connection(remote, tmp_path) as published:
        assert [
            row[2] for row in published.execute("PRAGMA index_info(story_art_references_by_art)")
        ] == ["locale", "art_id"]

    await Updater(remote).run([UpdateRequest("art", "v1", should_not_build)])
    assert called is False
    assert remote.pushes == 1


async def test_complete_art_builds_at_current_version_and_pushes_database_once(
    tmp_path,
    caplog,
):
    class CountingRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.pushes = 0

        async def push_database(self, source):
            self.pushes += 1
            await super().push_database(source)

    remote = CountingRemote()
    updater = Updater(remote)
    await updater.run([update_request(art_manifest("v3", "current"))])
    remote.pushes = 0
    caplog.clear()
    caplog.set_level("INFO", logger=updater_module.__name__)
    calls = []
    complete_manifest = ArtManifest(
        "v3",
        (
            replace(
                art_manifest("v1", "historical", category="background").arts[0],
                res_version="v1",
            ),
            art_manifest("v3", "current").arts[0],
        ),
        (),
    )

    async def build(active, force):
        calls.append((active, force))
        return complete_manifest

    result = await updater.run([UpdateRequest("art", "v3", build, complete=True)])

    assert result == (UpdateResult("art", "v3", "updated"),)
    assert calls == [("v3", False)]
    assert remote.pushes == 1
    records = [record for record in caplog.records if hasattr(record, "action")]
    assert (records[0].action, records[0].status) == ("apply", "done")
    assert (records[-1].action, records[-1].status) == ("publish", "done")
    assert [record.action for record in records].count("thumbnail") == 2
    assert [record.action for record in records].count("upload") == 4
    assert [record.status for record in records if record.action in {"apply", "publish"}] == [
        "done",
        "done",
    ]
    thumbnails = [record for record in records if record.action == "thumbnail"]
    assert sorted((record.current, record.total) for record in thumbnails) == [(1, 2), (2, 2)]
    assert all(record.res_version == "v3" for record in records)
    with database_connection(remote, tmp_path) as connection:
        assert {tuple(row) for row in connection.execute("SELECT category, art_id FROM arts")} == {
            ("background", "historical"),
            ("image", "current"),
        }
        assert dict(connection.execute("SELECT art_id, object_key FROM arts")) == {
            "historical": "ART/v1/composition/background/historical.png",
            "current": "ART/v3/composition/image/current.png",
        }
    assert set(remote.objects) >= {
        "ART/v1/composition/background/historical.png",
        "ART/v1/thumbnail/background/historical.webp",
        "ART/v3/composition/image/current.png",
        "ART/v3/thumbnail/image/current.webp",
    }


async def test_complete_art_cannot_be_combined_with_other_units_or_force():
    complete = UpdateRequest(
        "art", "v1", update_request(art_manifest("v1", "art")).build, complete=True
    )
    locale = update_request(locale_manifest("EN", "en-v1"))

    with pytest.raises(ValueError, match="sole requested"):
        await Updater(MemoryObjectStore()).run([complete, locale])
    with pytest.raises(ValueError, match="cannot be combined with force"):
        await Updater(MemoryObjectStore()).run([complete], force=True)


async def test_art_delta_overlays_only_the_same_category_qualified_identity(tmp_path):
    remote = MemoryObjectStore()
    updater = Updater(remote)
    await updater.run([update_request(art_manifest("v1", "shared", category="background"))])
    await updater.run(
        [
            update_request(
                ArtManifest(
                    "v2",
                    (
                        art_manifest("v2", "shared", category="image").arts[0],
                        art_manifest("v2", "new").arts[0],
                    ),
                    (),
                )
            )
        ]
    )

    with database_connection(remote, tmp_path) as connection:
        rows = [
            tuple(row)
            for row in connection.execute(
                "SELECT art_id, category FROM arts ORDER BY art_id, category"
            )
        ]
        assert rows == [
            ("new", "image"),
            ("shared", "background"),
            ("shared", "image"),
        ]
        assert (
            connection.execute(
                "SELECT res_version FROM unit_versions WHERE unit = 'art'"
            ).fetchone()[0]
            == "v2"
        )
    assert "ART/v1/composition/background/shared.png" in remote.objects
    assert "ART/v2/composition/image/shared.png" in remote.objects
    assert "ART/v2/composition/image/new.png" in remote.objects


async def test_character_sources_and_ordered_references_are_persisted(tmp_path):
    remote = MemoryObjectStore()
    manifest = character_manifest("v1", "amiya")

    await Updater(remote).run([update_request(manifest)])

    with database_connection(remote, tmp_path) as connection:
        assert tuple(
            connection.execute(
                "SELECT character_id, role, variant, width, height FROM source_arts"
            ).fetchone()
        ) == ("amiya", "body", "1", 2, 3)
        assert tuple(
            connection.execute(
                "SELECT art_id, position, source_art_id FROM art_source_refs"
            ).fetchone()
        ) == ("amiya#1$1", 0, "amiya:body:1")


async def test_source_art_identity_is_category_qualified(tmp_path):
    remote = MemoryObjectStore()
    image = PngArtifact.from_image(Image.new("RGBA", (2, 3), (1, 2, 3, 255)))
    sources = tuple(
        SourceArtRecord(
            id="shared-panel",
            category=category,
            kind="composite_panel",
            image=image,
        )
        for category in ("image", "background")
    )
    arts = tuple(
        ArtRecord(
            id=f"composite-{category}",
            category=category,
            image=image,
            source_art_references=(SourceArtReference(category, "shared-panel"),),
        )
        for category in ("image", "background")
    )

    await Updater(remote).run([update_request(ArtManifest("v1", arts=arts, source_arts=sources))])

    with database_connection(remote, tmp_path) as connection:
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT category, source_art_id, object_key FROM source_arts ORDER BY category"
            )
        ] == [
            (
                "background",
                "shared-panel",
                "ART/v1/source/background/shared-panel.png",
            ),
            ("image", "shared-panel", "ART/v1/source/image/shared-panel.png"),
        ]
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT category, source_category, source_art_id "
                "FROM art_source_refs ORDER BY category"
            )
        ] == [
            ("background", "background", "shared-panel"),
            ("image", "image", "shared-panel"),
        ]


async def test_art_delta_preserves_unmentioned_record_and_replaces_matching_identity(tmp_path):
    remote = MemoryObjectStore()
    await Updater(remote).run([update_request(art_manifest("v1", "fallback"))])

    await Updater(remote).run([update_request(art_manifest("v2", "different"))])
    with database_connection(remote, tmp_path) as connection:
        assert (
            connection.execute(
                "SELECT object_key FROM arts WHERE category = 'image' AND art_id = 'fallback'"
            ).fetchone()[0]
            == "ART/v1/composition/image/fallback.png"
        )

    await Updater(remote).run([update_request(art_manifest("v3", "fallback", (4, 5, 6, 255)))])
    with database_connection(remote, tmp_path) as connection:
        assert (
            connection.execute(
                "SELECT object_key FROM arts WHERE category = 'image' AND art_id = 'fallback'"
            ).fetchone()[0]
            == "ART/v3/composition/image/fallback.png"
        )


async def test_replacing_one_locale_preserves_other_units(tmp_path):
    remote = MemoryObjectStore()
    updater = Updater(remote)
    await updater.run(
        [
            update_request(locale_manifest("EN", "en-v1")),
            update_request(locale_manifest("JP", "jp-v1")),
        ]
    )

    await updater.run([update_request(locale_manifest("EN", "en-v2", suffix="two"))])

    with database_connection(remote, tmp_path) as connection:
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT unit, res_version FROM unit_versions ORDER BY unit"
            )
        ] == [("EN", "en-v2"), ("JP", "jp-v1")]
        assert [
            tuple(row)
            for row in connection.execute("SELECT locale, story_id FROM stories ORDER BY locale")
        ] == [("EN", "story_two"), ("JP", "story_one")]


async def test_all_requested_builds_are_atomic():
    remote = MemoryObjectStore()
    updater = Updater(remote)
    await updater.run([update_request(art_manifest("v1", "stable"))])
    original_database = remote.database
    original_objects = dict(remote.objects)

    async def fail(_active: str | None, _force: bool):
        raise RuntimeError("locale build failed")

    with pytest.raises(RuntimeError, match="locale build failed"):
        await updater.run(
            [
                update_request(art_manifest("v2", "candidate")),
                UpdateRequest("EN", "en-v1", fail),
            ]
        )

    assert remote.database == original_database
    assert remote.objects == original_objects


async def test_constraint_failure_publishes_none_of_the_requested_units():
    remote = MemoryObjectStore()
    updater = Updater(remote)
    await updater.run([update_request(art_manifest("v1", "stable"))])
    original_database = remote.database
    original_objects = dict(remote.objects)
    invalid = locale_manifest("EN", "en-v1")
    invalid = replace(
        invalid,
        archive_groups=(invalid.archive_groups[0], invalid.archive_groups[0]),
    )

    with pytest.raises(sqlite3.IntegrityError):
        await updater.run(
            [update_request(art_manifest("v2", "candidate")), update_request(invalid)]
        )

    assert remote.database == original_database
    assert remote.objects == original_objects


async def test_batch_upload_waits_for_build_and_sqlite_transaction(
    monkeypatch: pytest.MonkeyPatch,
):
    class GatedRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.upload_started = asyncio.Event()
            self.allow_upload = asyncio.Event()
            self.put_calls = 0
            self.push_calls = 0

        async def put_png(self, key, artifact):
            self.put_calls += 1
            self.upload_started.set()
            await self.allow_upload.wait()
            await super().put_png(key, artifact)

        async def push_database(self, source):
            self.push_calls += 1
            await super().push_database(source)

    remote = GatedRemote()
    manifest = art_manifest("v1", "candidate")
    build_started = asyncio.Event()
    allow_build_finish = asyncio.Event()
    transaction_applied = threading.Event()
    real_apply_changes = updater_module.apply_changes

    def apply_changes(*args, **kwargs):
        committed_object_keys = real_apply_changes(*args, **kwargs)
        transaction_applied.set()
        return committed_object_keys

    async def build(_active, _force):
        build_started.set()
        await allow_build_finish.wait()
        return manifest

    monkeypatch.setattr(updater_module, "apply_changes", apply_changes)
    run = asyncio.create_task(Updater(remote).run([UpdateRequest("art", "v1", build)]))
    await asyncio.wait_for(build_started.wait(), timeout=1)

    assert not run.done()
    assert remote.put_calls == 0
    assert remote.database is None
    assert remote.push_calls == 0

    allow_build_finish.set()
    await asyncio.wait_for(remote.upload_started.wait(), timeout=1)

    assert transaction_applied.is_set()
    assert remote.database is None
    assert remote.push_calls == 0

    remote.allow_upload.set()
    result = await asyncio.wait_for(run, timeout=1)

    assert result[0].status == "updated"
    assert remote.database is not None
    assert remote.push_calls == 1
    assert remote.put_calls == 1


async def test_final_artifact_batch_has_bounded_concurrency_and_one_upload_per_winner():
    class GatedRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.active = 0
            self.maximum_active = 0
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.keys: list[str] = []

        async def put_png(self, key, artifact):
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            self.keys.append(key)
            if self.active == 2:
                self.started.set()
            try:
                await self.release.wait()
                await super().put_png(key, artifact)
            finally:
                self.active -= 1

    remote = GatedRemote()
    manifest = ArtManifest(
        "v1",
        tuple(art_manifest("v1", f"winner-{index}").arts[0] for index in range(5)),
        (),
    )

    run = asyncio.create_task(Updater(remote, upload_workers=2).run([update_request(manifest)]))
    await asyncio.wait_for(remote.started.wait(), timeout=1)

    assert remote.maximum_active == 2
    assert len(remote.keys) == 2
    assert remote.database is None

    remote.release.set()
    await asyncio.wait_for(run, timeout=1)

    assert remote.maximum_active == 2
    assert len(remote.keys) == 5
    assert len(set(remote.keys)) == 5
    assert len(remote.objects) == 10


async def test_thumbnail_workers_generate_then_upload_one_image_at_a_time(monkeypatch):
    class GatedRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.active = 0

        async def put_thumbnail(self, key, thumbnail):
            self.active += 1
            if self.active == 2:
                self.started.set()
            await self.release.wait()
            await super().put_thumbnail(key, thumbnail)

    remote = GatedRemote()
    manifest = ArtManifest(
        "v1",
        tuple(art_manifest("v1", f"winner-{index}").arts[0] for index in range(5)),
        (),
    )
    generated = 0
    real_make_thumbnail = updater_module.make_thumbnail

    def counting_make_thumbnail(source):
        nonlocal generated
        generated += 1
        return real_make_thumbnail(source)

    monkeypatch.setattr(updater_module, "_THUMBNAIL_WORKERS", 2)
    monkeypatch.setattr(updater_module, "make_thumbnail", counting_make_thumbnail)
    run = asyncio.create_task(Updater(remote).run([update_request(manifest)]))
    await asyncio.wait_for(remote.started.wait(), timeout=1)

    assert generated == 2
    assert remote.database is None

    remote.release.set()
    await asyncio.wait_for(run, timeout=1)

    assert generated == 5


async def test_batch_upload_failure_prevents_database_publication():
    class FailingRemote(MemoryObjectStore):
        async def put_png(self, _key, _artifact):
            raise RuntimeError("batch upload failed")

    remote = FailingRemote()
    manifest = art_manifest("v1", "candidate")

    async def build(_active, _force):
        return manifest

    with pytest.raises(RuntimeError, match="batch upload failed"):
        await Updater(remote).run([UpdateRequest("art", "v1", build)])

    assert remote.database is None


async def test_thumbnail_upload_finishes_before_database_publication():
    class RecordingRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.events = []

        async def put_png(self, key, artifact):
            self.events.append(("png", key))
            await super().put_png(key, artifact)

        async def put_thumbnail(self, key, thumbnail):
            self.events.append(("thumbnail", key))
            await super().put_thumbnail(key, thumbnail)

        async def push_database(self, source):
            self.events.append(("database", DATABASE_OBJECT_KEY))
            await super().push_database(source)

    remote = RecordingRemote()

    await Updater(remote).run([update_request(art_manifest("v1", "candidate"))])

    assert remote.events == [
        ("png", "ART/v1/composition/image/candidate.png"),
        ("thumbnail", "ART/v1/thumbnail/image/candidate.webp"),
        ("database", DATABASE_OBJECT_KEY),
    ]


async def test_thumbnail_upload_failure_prevents_database_publication():
    class FailingRemote(MemoryObjectStore):
        async def put_thumbnail(self, _key, _thumbnail):
            raise RuntimeError("thumbnail upload failed")

    remote = FailingRemote()

    with pytest.raises(RuntimeError, match="thumbnail upload failed"):
        await Updater(remote).run([update_request(art_manifest("v1", "candidate"))])

    assert remote.database is None
    assert "ART/v1/composition/image/candidate.png" in remote.objects


async def test_database_push_failure_can_retry_mutable_thumbnail_publication():
    class FailOnceRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.thumbnail_puts = 0
            self.database_pushes = 0

        async def put_thumbnail(self, key, content):
            self.thumbnail_puts += 1
            await super().put_thumbnail(key, content)

        async def push_database(self, source):
            self.database_pushes += 1
            if self.database_pushes == 1:
                raise RuntimeError("database push failed")
            await super().push_database(source)

    remote = FailOnceRemote()
    update = update_request(art_manifest("v1", "candidate"))

    with pytest.raises(RuntimeError, match="database push failed"):
        await Updater(remote).run([update])
    result = await Updater(remote).run([update])

    assert result == (UpdateResult("art", "v1", "updated"),)
    assert remote.thumbnail_puts == 2
    assert remote.database is not None


async def test_thumbnail_failure_logs_only_terminal_status_and_publishes_nothing(
    monkeypatch,
    caplog,
):
    def fail(_source):
        raise RuntimeError("thumbnail generation failed")

    monkeypatch.setattr(updater_module, "make_thumbnail", fail)
    remote = MemoryObjectStore()
    caplog.set_level("INFO", logger=updater_module.__name__)

    with pytest.raises(RuntimeError, match="thumbnail generation failed"):
        await Updater(remote).run([update_request(art_manifest("v1", "candidate"))])

    records = [
        record for record in caplog.records if getattr(record, "action", None) == "thumbnail"
    ]
    assert [(record.status, record.current, record.total) for record in records] == [
        ("failed", 1, 1)
    ]
    assert set(remote.objects) == {"ART/v1/composition/image/candidate.png"}
    assert remote.database is None


async def test_batch_upload_failure_drains_already_started_uploads():
    class DrainingRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.started = 0
            self.both_started = asyncio.Event()
            self.failed = asyncio.Event()
            self.release_survivor = asyncio.Event()

        async def put_png(self, key, artifact):
            self.started += 1
            if self.started == 2:
                self.both_started.set()
            await self.both_started.wait()
            if "/fail.png" in key:
                self.failed.set()
                raise RuntimeError("batch upload failed")
            await self.release_survivor.wait()
            await super().put_png(key, artifact)

    remote = DrainingRemote()
    manifest = ArtManifest(
        "v1",
        (
            art_manifest("v1", "fail").arts[0],
            art_manifest("v1", "survivor").arts[0],
        ),
        (),
    )
    run = asyncio.create_task(Updater(remote, upload_workers=2).run([update_request(manifest)]))

    await asyncio.wait_for(remote.failed.wait(), timeout=1)
    assert not run.done()

    remote.release_survivor.set()
    with pytest.raises(RuntimeError, match="batch upload failed"):
        await asyncio.wait_for(run, timeout=1)

    assert len(remote.objects) == 1
    assert remote.database is None


async def test_batch_cancellation_drains_already_started_uploads():
    class BlockingRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def put_png(self, key, artifact):
            self.started.set()
            await self.release.wait()
            await super().put_png(key, artifact)

    remote = BlockingRemote()
    run = asyncio.create_task(
        Updater(remote).run([update_request(art_manifest("v1", "candidate"))])
    )
    await asyncio.wait_for(remote.started.wait(), timeout=1)

    run.cancel()
    await asyncio.sleep(0)
    assert not run.done()

    run.cancel()
    await asyncio.sleep(0)
    assert not run.done()

    remote.release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(run, timeout=1)

    assert remote.database is None


async def test_cancellation_waits_for_database_push_before_removing_local_file():
    class BlockingRemote(MemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.source = None

        async def push_database(self, source):
            self.source = source
            self.started.set()
            await self.release.wait()
            await super().push_database(source)

    remote = BlockingRemote()
    run = asyncio.create_task(
        Updater(remote).run([update_request(locale_manifest("EN", "en-v1", art_id="absent"))])
    )
    await asyncio.wait_for(remote.started.wait(), timeout=1)
    assert remote.source is not None

    run.cancel()
    await asyncio.sleep(0)
    assert not run.done()
    assert remote.source.is_file()

    run.cancel()
    await asyncio.sleep(0)
    assert not run.done()
    assert remote.source.is_file()

    remote.release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(run, timeout=1)

    assert remote.database is not None
    assert not remote.source.exists()


async def test_force_art_at_a_new_version_is_rejected_before_building_or_copying_objects():
    remote = MemoryObjectStore()
    updater = Updater(remote)
    first = art_manifest("v1", "same", (1, 2, 3, 255))
    second = art_manifest("v2", "same", (4, 5, 6, 255))
    await updater.run([update_request(first)])
    original_database = remote.database
    original_objects = remote.objects.copy()
    built = False

    async def build(_active: str | None, _force: bool):
        nonlocal built
        built = True
        return second

    with pytest.raises(ValueError, match="force is not supported for art updates"):
        await updater.run([UpdateRequest("art", "v2", build)], force=True)

    assert built is False
    assert remote.database == original_database
    assert remote.objects == original_objects


async def test_png_upload_failure_keeps_previous_database():
    class FailingRemote(MemoryObjectStore):
        fail = False

        async def put_png(self, key, artifact):
            if self.fail:
                raise RuntimeError("upload failed")
            await super().put_png(key, artifact)

    remote = FailingRemote()
    updater = Updater(remote)
    await updater.run([update_request(art_manifest("v1", "stable"))])
    original_database = remote.database
    remote.fail = True

    with pytest.raises(RuntimeError, match="upload failed"):
        await updater.run([update_request(art_manifest("v2", "candidate"))])

    assert remote.database == original_database


def test_schema_rejects_non_string_story_reference_names(tmp_path):
    path = tmp_path / "arkwaifu.sqlite3"
    initialize_or_validate(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute("INSERT INTO unit_versions VALUES ('EN', 'en-v1')")
        connection.execute(
            "INSERT INTO story_collections VALUES ('EN', 'archive_group:group', 'archive_group')"
        )
        connection.execute(
            "INSERT INTO archive_groups VALUES "
            "('EN', 'group', 'archive_group:group', 0, 'Group', 'others', NULL)"
        )
        connection.execute(
            """
            INSERT INTO stories VALUES
                ('EN', 'story', 'archive_group:group', 'before', '', '', 'Story', '', 0)
            """
        )

        with pytest.raises(sqlite3.IntegrityError, match="names must be strings"):
            connection.execute(
                """
                INSERT INTO story_art_references VALUES
                    ('EN', 'story', 0, 'art', 'picture', 'image', NULL, NULL,
                     '["valid", 1]')
                """
            )
    finally:
        connection.close()
