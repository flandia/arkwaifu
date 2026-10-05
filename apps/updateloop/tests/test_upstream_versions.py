"""Exercise bounded retries through the real artwork and locale version detectors."""

import httpx
import pytest

from arkwaifu_updateloop.upstream import artwork as artwork_module
from arkwaifu_updateloop.upstream import version as version_module
from arkwaifu_updateloop.upstream.artwork import UpstreamArtworkBuilder
from arkwaifu_updateloop.upstream.cache import UpstreamCache
from arkwaifu_updateloop.upstream.locale import UpstreamLocaleBuilder


@pytest.mark.parametrize("unit", ["artwork", "EN"])
async def test_version_detectors_retry_reads_without_downloading_snapshots(
    unit, tmp_path, monkeypatch
):
    calls, waits = [], []

    async def sleep(delay):
        waits.append(delay)

    async def respond(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("temporary", request=request)
        if len(calls) == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"resVersion": "current", "versionId": "current"})

    monkeypatch.setattr(version_module.asyncio, "sleep", sleep)
    if unit == "artwork":
        client = httpx.AsyncClient
        monkeypatch.setattr(
            artwork_module.httpx,
            "AsyncClient",
            lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
        )
        builder = UpstreamArtworkBuilder(
            version_url="https://upstream.test/version",
            asset_base_url="unused",
            cache=UpstreamCache(tmp_path / "cache"),
        )
        assert await builder.detect_version() == "current"
    else:
        builder = UpstreamLocaleBuilder(
            github_token="workflow-token",
            transport=httpx.MockTransport(respond),
        )
        assert await builder.detect_version(unit) == "current"
        assert builder._detected_versions == {unit: "current"}
        assert all(request.headers["authorization"] == "Bearer workflow-token" for request in calls)
        assert all("hot_update_list.json" in request.url.path for request in calls)
        await builder.aclose()
    assert len(calls) == 3
    assert waits == [5, 10]


@pytest.mark.parametrize(
    "status,headers,attempts,waits",
    [
        (429, {"Retry-After": "2"}, 3, [2, 2]),
        (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "130"}, 3, [30, 30]),
        (429, {"Retry-After": "120"}, 1, []),
        (403, {}, 1, []),
        (401, {}, 1, []),
        (404, {}, 1, []),
        (503, {}, 3, [5, 10]),
    ],
)
async def test_retry_budget_and_permanent_errors(status, headers, attempts, waits, monkeypatch):
    requests, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    def respond(request):
        requests.append(request)
        return httpx.Response(status, headers=headers)

    monkeypatch.setattr(version_module.asyncio, "sleep", sleep)
    monkeypatch.setattr(version_module.time, "time", lambda: 100)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await version_module.version_response(client, "https://upstream.test/version")
    assert len(requests) == attempts
    assert delays == waits


@pytest.mark.parametrize("retry_after,attempts,waits", [(50, 3, [50, 10]), (60, 2, [60])])
async def test_transport_errors_share_the_rate_limit_wait_budget(
    retry_after, attempts, waits, monkeypatch
):
    requests, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": str(retry_after)})
        raise httpx.ConnectTimeout("temporary", request=request)

    monkeypatch.setattr(version_module.asyncio, "sleep", sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(httpx.ConnectTimeout, match="temporary"):
            await version_module.version_response(client, "https://upstream.test/version")
    assert len(requests) == attempts
    assert delays == waits


async def test_malformed_version_is_not_retried(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"versionId": ""})

    builder = UpstreamLocaleBuilder(transport=httpx.MockTransport(respond))
    with pytest.raises(TypeError, match="versionId"):
        await builder.detect_version("CN")
    assert len(calls) == 1
    assert builder._detected_versions == {}
    await builder.aclose()
