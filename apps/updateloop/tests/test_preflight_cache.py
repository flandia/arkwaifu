import io
import json
import sqlite3
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from arkwaifu_updateloop import S3ObjectStore, Updater, UpdateRequest
from arkwaifu_updateloop import object_store as remote
from arkwaifu_updateloop.database import initialize_or_validate


class Client:
    def __init__(self, database):
        self.database = database
        self.etag = '"generation-1"'
        self.meta = SimpleNamespace(endpoint_url="https://objects.example")
        self.heads = 0
        self.downloads = []
        self.error = None
        self.response_etag = None
        self.download_error = None
        self.truncate = False
        self.body = None

    def head_object(self, **kwargs):
        assert kwargs == {"Bucket": "archive", "Key": "arkwaifu.sqlite3"}
        self.heads += 1
        if self.error:
            raise self.error
        return {"ETag": self.etag, "ContentLength": len(self.database)}

    def get_object(self, **kwargs):
        assert kwargs["IfMatch"] == self.etag
        self.downloads.append(kwargs)
        if self.download_error:
            raise self.download_error
        self.body = io.BytesIO(self.database[:-1] if self.truncate else self.database)
        return {
            "ETag": self.response_etag or self.etag,
            "ContentLength": len(self.database),
            "Body": self.body,
        }


@pytest.fixture
def cached_store(monkeypatch, tmp_path):
    source = tmp_path / "source.sqlite3"
    initialize_or_validate(source)
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO unit_versions VALUES ('CN', 'v1')")
    client = Client(source.read_bytes())
    monkeypatch.setattr(remote.boto3, "client", lambda *args, **kwargs: client)
    cache = tmp_path / "cache"
    store = S3ObjectStore(
        bucket="archive",
        region="region",
        access_key_id="access",
        secret_access_key="secret",
        database_cache_dir=cache,
    )
    return store, client, cache, source


async def test_cache_hit_rechecks_origin_and_uses_an_unchanged_copy(cached_store, tmp_path):
    store, client, cache, _source = cached_store
    destination = tmp_path / "check.sqlite3"
    assert await store.pull_database(destination)
    first_key = store.database_cache_key
    with sqlite3.connect(destination) as connection:
        connection.execute("DELETE FROM unit_versions")
    assert await store.pull_database(destination)
    assert destination.read_bytes() == client.database
    assert (cache / "published/database/arkwaifu.sqlite3").read_bytes() == client.database
    assert store.database_cache_key == first_key
    assert client.heads == 2
    assert len(client.downloads) == 1
    assert client.body.closed


async def test_changed_etag_refreshes_the_cached_generation(cached_store, tmp_path):
    store, client, _cache, source = cached_store
    destination = tmp_path / "check.sqlite3"
    await store.pull_database(destination)
    first_key = store.database_cache_key
    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE unit_versions SET res_version='v2'")
    client.database = source.read_bytes()
    client.etag = '"generation-2"'
    await store.pull_database(destination)
    assert destination.read_bytes() == client.database
    assert store.database_cache_key != first_key
    assert len(client.downloads) == 2


@pytest.mark.parametrize("damage", ["bytes", "truncated", "metadata", "missing"])
async def test_corrupt_cache_is_repaired_with_a_new_save_key(cached_store, tmp_path, damage):
    store, client, cache, _source = cached_store
    destination = tmp_path / "check.sqlite3"
    await store.pull_database(destination)
    first_key = store.database_cache_key
    directory = cache / "published/database"
    if damage == "bytes":
        content = bytearray((directory / "arkwaifu.sqlite3").read_bytes())
        content[-1] ^= 1
        (directory / "arkwaifu.sqlite3").write_bytes(content)
    elif damage == "truncated":
        (directory / "arkwaifu.sqlite3").write_bytes(b"partial")
    elif damage == "metadata":
        (directory / "metadata.json").write_text("{}")
    else:
        (directory / "arkwaifu.sqlite3").unlink()
    await store.pull_database(destination)
    assert destination.read_bytes() == client.database
    assert store.database_cache_key != first_key
    assert len(client.downloads) == 2


@pytest.mark.parametrize("status", [404, 403, 503])
async def test_origin_failure_never_uses_a_stale_cache(cached_store, tmp_path, status):
    store, client, _cache, _source = cached_store
    destination = tmp_path / "check.sqlite3"
    await store.pull_database(destination)
    client.error = ClientError({"Error": {"Code": str(status)}}, "HeadObject")
    if status == 404:
        assert not await store.pull_database(destination)
        assert not destination.exists()
    else:
        with pytest.raises(ClientError):
            await store.pull_database(destination)
    assert store.database_cache_key is None
    assert len(client.downloads) == 1


async def test_replaced_origin_during_download_does_not_replace_cache(cached_store, tmp_path):
    store, client, cache, _source = cached_store
    destination = tmp_path / "check.sqlite3"
    await store.pull_database(destination)
    before = (cache / "published/database/metadata.json").read_bytes()
    client.etag = '"generation-2"'
    client.response_etag = '"unexpected-generation"'
    with pytest.raises(ValueError, match="changed"):
        await store.pull_database(destination)
    assert (cache / "published/database/metadata.json").read_bytes() == before
    assert client.body.closed
    assert store.database_cache_key is None


@pytest.mark.parametrize("failure", ["precondition", "truncated"])
async def test_failed_refresh_keeps_the_previous_cache(cached_store, tmp_path, failure):
    store, client, cache, _source = cached_store
    destination = tmp_path / "check.sqlite3"
    await store.pull_database(destination)
    before = (cache / "published/database/metadata.json").read_bytes()
    client.etag = '"generation-2"'
    if failure == "precondition":
        client.download_error = ClientError({"Error": {"Code": "PreconditionFailed"}}, "GetObject")
        expected = ClientError
    else:
        client.truncate = True
        expected = ValueError
    with pytest.raises(expected):
        await store.pull_database(destination)
    assert (cache / "published/database/metadata.json").read_bytes() == before
    assert (cache / "published/database/arkwaifu.sqlite3").read_bytes() == client.database
    assert client.body.closed
    assert store.database_cache_key is None


@pytest.mark.parametrize("etag,size", [("", 100), (None, 100), ('"v1"', 0), ('"v1"', True)])
async def test_invalid_origin_metadata_cannot_authorize_reuse(cached_store, tmp_path, etag, size):
    store, client, _cache, _source = cached_store
    destination = tmp_path / "check.sqlite3"
    await store.pull_database(destination)
    client.head_object = lambda **_: {"ETag": etag, "ContentLength": size}
    with pytest.raises(ValueError, match="metadata"):
        await store.pull_database(destination)
    assert len(client.downloads) == 1
    assert store.database_cache_key is None


async def test_cache_is_bound_to_the_source_endpoint(cached_store, tmp_path):
    store, client, _cache, _source = cached_store
    destination = tmp_path / "check.sqlite3"
    await store.pull_database(destination)
    first_key = store.database_cache_key
    client.meta.endpoint_url = "https://another-source.example"
    await store.pull_database(destination)
    assert store.database_cache_key != first_key
    assert len(client.downloads) == 2


@pytest.mark.parametrize("state", ["current", "repair", "invalid"])
async def test_cached_checks_preserve_schema_validation_and_repair_detection(cached_store, state):
    store, client, cache, source = cached_store
    with sqlite3.connect(source) as connection:
        if state == "repair":
            connection.execute("DROP INDEX story_narrative_image_references_by_asset")
        elif state == "invalid":
            connection.execute("PRAGMA user_version=99")
    client.database = source.read_bytes()

    async def build():
        raise AssertionError("check must not build")

    updater = Updater(store)
    requests = [UpdateRequest("CN", "v1", build)]
    for _ in range(2):
        if state == "invalid":
            with pytest.raises(ValueError, match="schema version"):
                await updater.needs_update(requests)
        else:
            assert await updater.needs_update(requests) is (state == "repair")
        assert (cache / "published/database/arkwaifu.sqlite3").read_bytes() == client.database
    assert len(client.downloads) == 1
    assert "cache_key" in json.loads((cache / "published/database/metadata.json").read_text())
