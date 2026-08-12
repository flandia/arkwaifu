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
    Update,
    Updateloop,
)
from arkwaifu_updateloop.domain import (
    ArtManifest,
    ArtRecord,
    Gallery,
    GalleryEntry,
    LocaleManifest,
    PngArtifact,
    StoryArtReference,
    StoryGroupRecord,
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


def _art(version: str) -> ArtManifest:
    return ArtManifest(
        version,
        (
            ArtRecord(
                "fixture",
                "image",
                PngArtifact.from_image(Image.new("RGBA", (3, 5), (10, 20, 30, 255))),
            ),
        ),
        (),
    )


def _locale(version: str) -> LocaleManifest:
    return LocaleManifest(
        "EN",
        version,
        (
            StoryGroupRecord(
                "group",
                "Group",
                "major_event",
                (
                    StoryRecord(
                        "story",
                        "group",
                        "before",
                        "Before Operation",
                        "1",
                        "Story",
                        "Info",
                        (StoryArtReference("fixture", "picture", "image"),),
                    ),
                ),
            ),
        ),
        (Gallery("gallery", "Gallery", "", (GalleryEntry("entry", 0, "", "", "fixture"),)),),
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
    art = _art(f"art-{uuid4().hex}")
    locale = _locale(f"en-{uuid4().hex}")

    async def build_art(_active, _force):
        return art

    async def build_locale(_active, _force):
        return locale

    result = await Updateloop(remote).run(
        [
            Update("art", art.upstream_version, build_art),
            Update("EN", locale.upstream_version, build_locale),
        ]
    )

    assert [value.status for value in result] == ["updated", "updated"]
    database_path = tmp_path / DATABASE_OBJECT_KEY
    assert await remote.pull_database(database_path) is True
    with sqlite3.connect(database_path) as connection:
        assert list(
            connection.execute("SELECT unit, res_version FROM unit_versions ORDER BY unit")
        ) == [("EN", locale.upstream_version), ("art", art.upstream_version)]
        object_key = connection.execute(
            "SELECT object_key FROM arts WHERE art_id = 'fixture'"
        ).fetchone()[0]
    head = client.head_object(Bucket=bucket, Key=object_key)
    assert head["ContentType"] == "image/png"
    assert head["CacheControl"] == "public, max-age=31536000, immutable"
    assert head["Metadata"] == {}
    assert object_key == (f"ART/{art.upstream_version}/composition/image/fixture.png")
    database_head = client.head_object(Bucket=bucket, Key=DATABASE_OBJECT_KEY)
    assert database_head["ContentType"] == "application/vnd.sqlite3"
    assert database_head["CacheControl"] == "no-cache"
