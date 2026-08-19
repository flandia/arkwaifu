from __future__ import annotations

import os
import sqlite3
from uuid import uuid4

import boto3
import pytest
from botocore.config import Config
from PIL import Image

from arkwaifu_updateloop import (
    DATABASE_OBJECT_KEY,
    S3ObjectStore,
    Updater,
    UpdateRequest,
)
from arkwaifu_updateloop.domain import (
    ArchiveGroup,
    ArtworkManifest,
    ArtworkRecord,
    Gallery,
    GalleryArtwork,
    GalleryGroup,
    LocaleManifest,
    PngArtifact,
    StoryArtworkReference,
    StoryRecord,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("ARKWAIFU_INTEGRATION") != "1",
    reason="set ARKWAIFU_INTEGRATION=1 to run Docker integration tests",
)

_ENDPOINT = os.environ.get("ARKWAIFU_TEST_S3_ENDPOINT_URL", "http://127.0.0.1:59000")
_ACCESS_KEY = os.environ.get("ARKWAIFU_TEST_S3_ACCESS_KEY_ID", "arkwaifu")
_SECRET_KEY = os.environ.get("ARKWAIFU_TEST_S3_SECRET_ACCESS_KEY", "arkwaifu-dev-secret")


@pytest.fixture
def isolated_bucket():
    bucket = f"arkwaifu-test-{uuid4().hex}"
    client = boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id=_ACCESS_KEY,
        aws_secret_access_key=_SECRET_KEY,
        config=Config(s3={"addressing_style": "path"}),
    )
    client.create_bucket(Bucket=bucket)
    client.put_bucket_versioning(
        Bucket=bucket,
        VersioningConfiguration={"Status": "Enabled"},
    )
    try:
        yield bucket, client
    finally:
        response = client.list_object_versions(Bucket=bucket)
        objects = [
            {"Key": value["Key"], "VersionId": value["VersionId"]}
            for collection in ("Versions", "DeleteMarkers")
            for value in response.get(collection, [])
        ]
        if objects:
            client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
        client.delete_bucket(Bucket=bucket)


def _artwork(version: str) -> ArtworkManifest:
    return ArtworkManifest(
        version,
        (
            ArtworkRecord(
                "fixture",
                "illustration",
                PngArtifact.from_image(Image.new("RGBA", (3, 5), (10, 20, 30, 255))),
            ),
        ),
        (),
    )


def _locale(version: str) -> LocaleManifest:
    return LocaleManifest(
        unit="EN",
        upstream_version=version,
        movements=(),
        sections=(),
        archive_groups=(
            ArchiveGroup(
                id="group",
                collection_id="archive_group:group",
                position=0,
                name="Group",
                archive_category="events",
                story_type="side_story",
                stories=(
                    StoryRecord(
                        id="story",
                        collection_id="archive_group:group",
                        tag="before",
                        tag_text="Before Operation",
                        code="1",
                        name="Story",
                        info="Info",
                        artwork_references=(
                            StoryArtworkReference("fixture", "picture", "illustration"),
                        ),
                    ),
                ),
            ),
        ),
        galleries=(
            Gallery(
                id="gallery",
                collection_id="archive_group:group",
                position=0,
                name="Gallery",
                description="",
                location_id=None,
                groups=(
                    GalleryGroup(
                        id="entry",
                        position=0,
                        name="",
                        description="",
                        related_story_id="story",
                        related_stage_id=None,
                        artworks=(
                            GalleryArtwork(
                                position=0,
                                cg_id="fixture",
                                asset_id="fixture",
                                category="illustration",
                                layout="none",
                                panels=(),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


async def test_monolithic_database_and_pngs_publish_to_minio(isolated_bucket, tmp_path):
    bucket, client = isolated_bucket
    remote = S3ObjectStore(
        bucket=bucket,
        region="us-east-1",
        access_key_id=_ACCESS_KEY,
        secret_access_key=_SECRET_KEY,
        endpoint_url=_ENDPOINT,
        path_style=True,
    )
    artwork = _artwork(f"artwork-{uuid4().hex}")
    locale = _locale(f"en-{uuid4().hex}")

    async def build_artwork(_active, _force):
        return artwork

    async def build_locale(_active, _force):
        return locale

    result = await Updater(remote).run(
        [
            UpdateRequest("artwork", artwork.upstream_version, build_artwork),
            UpdateRequest("EN", locale.upstream_version, build_locale),
        ]
    )

    assert [value.status for value in result] == ["updated", "updated"]
    database_path = tmp_path / DATABASE_OBJECT_KEY
    assert await remote.pull_database(database_path) is True
    with sqlite3.connect(database_path) as connection:
        assert list(
            connection.execute("SELECT unit, res_version FROM unit_versions ORDER BY unit")
        ) == [("EN", locale.upstream_version), ("artwork", artwork.upstream_version)]
        object_key = connection.execute(
            "SELECT object_key FROM narrative_image_assets WHERE asset_id = 'fixture'"
        ).fetchone()[0]
    head = client.head_object(Bucket=bucket, Key=object_key)
    assert head["ContentType"] == "image/png"
    assert head["CacheControl"] == "public, max-age=31536000, immutable"
    assert head["Metadata"] == {}
    assert object_key == (f"ART/{artwork.upstream_version}/composition/image/fixture.png")
    thumbnail_key = f"ART/{artwork.upstream_version}/thumbnail/illustration/fixture.webp"
    thumbnail_head = client.head_object(Bucket=bucket, Key=thumbnail_key)
    assert thumbnail_head["ContentType"] == "image/webp"
    assert thumbnail_head.get("CacheControl") is None
    assert thumbnail_head["Metadata"] == {}
    database_head = client.head_object(Bucket=bucket, Key=DATABASE_OBJECT_KEY)
    assert database_head["ContentType"] == "application/vnd.sqlite3"
    assert database_head["CacheControl"] == "no-cache"
