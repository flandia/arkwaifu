import hashlib
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest
from botocore.exceptions import ClientError

from arkwaifu_updateloop import asset_bundle_archive as archive_module
from arkwaifu_updateloop.asset_bundle_archive import (
    MemoryAssetBundleArchiveStore,
    S3AssetBundleArchiveStore,
)
from arkwaifu_updateloop.upstream import artwork as artwork_module
from arkwaifu_updateloop.upstream.artwork import UpstreamArtworkBuilder
from arkwaifu_updateloop.upstream.cache import UpstreamCache


def _md5(content: bytes) -> str:
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


def _manifest(resources: dict[str, bytes]) -> bytes:
    return json.dumps(
        {"abInfos": [{"name": name, "md5": _md5(content)} for name, content in resources.items()]},
        separators=(",", ":"),
    ).encode()


def _wrapper(name: str, content: bytes) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(name, content)
    return output.getvalue()


def _mock_artwork_client(
    monkeypatch: pytest.MonkeyPatch,
    versions: dict[str, dict[str, bytes]],
    requests: list[str],
) -> None:
    real_client = httpx.AsyncClient

    async def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path.strip("/")
        requests.append(path)
        version, filename = path.split("/", 1)
        resources = versions[version]
        if filename == "hot_update_list.json":
            return httpx.Response(200, content=_manifest(resources))
        logical_names = {artwork_module._resource_filename(name): name for name in resources}
        name = logical_names[filename]
        return httpx.Response(200, content=_wrapper(name, resources[name]))

    monkeypatch.setattr(
        artwork_module.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(respond),
            **kwargs,
        ),
    )


def test_archive_manifest_accepts_short_anon_digest():
    resources = UpstreamArtworkBuilder._parse_all_resources(
        {
            "abInfos": [
                {
                    "name": "anon/f97e80db75bb062d98254cfb40e2d578.bin",
                    "md5": "26A8",
                }
            ]
        },
        "v1",
    )

    assert [(resource.name, resource.md5) for resource in resources] == [
        ("anon/f97e80db75bb062d98254cfb40e2d578.bin", "26a8")
    ]


def test_archive_manifest_rejects_short_digest_for_other_resources():
    with pytest.raises(ValueError, match="invalid MD5"):
        UpstreamArtworkBuilder._parse_all_resources(
            {
                "abInfos": [
                    {
                        "name": "avg/bg/example.ab",
                        "md5": "26A8",
                    }
                ]
            },
            "v1",
        )


@pytest.mark.asyncio
async def test_first_archive_builds_full_history_then_resumes_from_last_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    versions = {
        "v1": {
            "a.ab": b"a-v1",
            "nested/b.ab": b"b-v1",
        },
        "v2": {
            "a.ab": b"a-v1",
            "nested/b.ab": b"b-v2",
            "c.ab": b"c-v2",
        },
    }
    requests: list[str] = []
    _mock_artwork_client(monkeypatch, versions, requests)
    builder = UpstreamArtworkBuilder(
        version_url="https://version.example",
        asset_base_url="https://assets.example",
        cache=UpstreamCache(tmp_path / ".cache"),
        download_workers=2,
    )
    archive = MemoryAssetBundleArchiveStore()

    await builder.archive_history(("v1", "v2"), archive)

    assert await archive.completed_versions() == frozenset({"v1", "v2"})
    assert set(archive.objects) == {
        "v1/a.dat",
        "v1/nested_b.dat",
        "v1/hot_update_list.json",
        "v2/nested_b.dat",
        "v2/c.dat",
        "v2/hot_update_list.json",
    }
    assert requests.count("v1/a.dat") == 1
    assert "v2/a.dat" not in requests

    requests.clear()
    versions["v3"] = {
        "a.ab": b"a-v3",
        "nested/b.ab": b"b-v2",
        "c.ab": b"c-v2",
    }
    await builder.archive_history(("v1", "v2", "v3"), archive)

    assert requests == ["v3/hot_update_list.json", "v3/a.dat"]
    assert "v3/a.dat" in archive.objects
    assert "v3/hot_update_list.json" in archive.objects


@pytest.mark.asyncio
async def test_bundle_failure_does_not_publish_completion_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    versions = {"v1": {"a.ab": b"a-v1"}}
    _mock_artwork_client(monkeypatch, versions, [])

    class FailingArchive(MemoryAssetBundleArchiveStore):
        async def put_bundle(self, version, filename, source, *, bundle_md5):
            raise RuntimeError("archive upload failed")

    archive = FailingArchive()
    builder = UpstreamArtworkBuilder(
        version_url="https://version.example",
        asset_base_url="https://assets.example",
        cache=UpstreamCache(tmp_path / ".cache"),
    )

    with pytest.raises(RuntimeError, match="archive upload failed"):
        await builder.archive_history(("v1",), archive)

    assert await archive.completed_versions() == frozenset()


class _S3Client:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, object]] = {}

    def list_objects_v2(self, **request):
        prefix = request["Prefix"]
        version_prefixes = {
            f"{prefix}{key.removeprefix(prefix).split('/', 1)[0]}/"
            for key in self.objects
            if key.startswith(prefix)
        }
        return {
            "IsTruncated": False,
            "CommonPrefixes": [{"Prefix": value} for value in sorted(version_prefixes)],
        }

    def head_object(self, *, Bucket, Key):
        try:
            return self.objects[Key]
        except KeyError as error:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject") from error

    def put_object(self, **request):
        content = request["Body"].read()
        self.objects[request["Key"]] = {
            "BodyBytes": content,
            "ContentLength": request["ContentLength"],
            "ContentType": request["ContentType"],
            "CacheControl": request["CacheControl"],
            "Metadata": request["Metadata"],
        }

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key]["BodyBytes"])}


@pytest.mark.asyncio
async def test_s3_archive_uses_cn_windows_prefix_and_create_only_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    client = _S3Client()
    monkeypatch.setattr(archive_module.boto3, "client", lambda *_args, **_kwargs: client)
    store = S3AssetBundleArchiveStore(
        bucket="arkwaifu-ab",
        region="sgp1",
        access_key_id="access",
        secret_access_key="secret",
        endpoint_url="https://sgp1.digitaloceanspaces.com",
    )
    bundle = tmp_path / "[uc]shaders shadow 1.dat"
    bundle.write_bytes(b"wrapper")
    manifest = tmp_path / "hot_update_list.json"
    manifest.write_bytes(b'{"abInfos":[]}')
    bundle_md5 = _md5(b"inner bundle")

    assert await store.put_bundle("v1", "[uc]shaders shadow 1.dat", bundle, bundle_md5=bundle_md5)
    assert await store.put_manifest("v1", manifest)
    assert not await store.put_bundle(
        "v1", "[uc]shaders shadow 1.dat", bundle, bundle_md5=bundle_md5
    )

    assert await store.completed_versions() == frozenset({"v1"})
    assert await store.read_manifest("v1") == manifest.read_bytes()
    assert set(client.objects) == {
        "CN/Windows/v1/[uc]shaders shadow 1.dat",
        "CN/Windows/v1/hot_update_list.json",
    }
    metadata = client.objects["CN/Windows/v1/[uc]shaders shadow 1.dat"]["Metadata"]
    assert metadata == {
        "manifest-md5": bundle_md5,
        "sha256": hashlib.sha256(b"wrapper").hexdigest(),
    }

    bundle.write_bytes(b"conflicting wrapper")
    with pytest.raises(ValueError, match="immutable asset-bundle archive object conflicts"):
        await store.put_bundle("v1", "[uc]shaders shadow 1.dat", bundle, bundle_md5=bundle_md5)
