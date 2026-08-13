from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
import pytest

from arkwaifu_updateloop.upstream.art_history import WindowsVersionHistory
from arkwaifu_updateloop.upstream.cache import UpstreamCache

_CURRENT = "26-08-07-10-51-39_26e0fc"
_MIDDLE = "26-05-27-13-34-07_688e6e"
_EARLIEST = "26-03-09-09-45-56_fd97a4"


def _history(
    tmp_path: Path,
    respond,
    *,
    token: str | None = "github-secret",
) -> WindowsVersionHistory:
    return WindowsVersionHistory(
        "https://api.github.test",
        "https://raw.github.test",
        token,
        UpstreamCache(tmp_path / ".cache"),
        httpx.MockTransport(respond),
    )


@pytest.mark.asyncio
async def test_history_pages_orders_deduplicates_and_appends_current(tmp_path: Path):
    first_page = [
        {"sha": f"duplicate-{index}" if index < 2 else f"padding-{index}"} for index in range(100)
    ]
    raw_versions = {
        "duplicate-0": _MIDDLE,
        "duplicate-1": _MIDDLE,
        **{f"padding-{index}": _EARLIEST for index in range(2, 100)},
        "oldest": _EARLIEST,
    }
    api_pages: list[int] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.test":
            assert request.headers["authorization"] == "Bearer github-secret"
            assert request.url.params["path"] == "conf/version_windows.json"
            assert request.url.params["per_page"] == "100"
            page = int(request.url.params["page"])
            api_pages.append(page)
            return httpx.Response(200, json=first_page if page == 1 else [{"sha": "oldest"}])
        assert request.url.host == "raw.github.test"
        assert "authorization" not in request.headers
        revision = request.url.path.split("/")[3]
        return httpx.Response(200, json={"version": {"resVersion": raw_versions[revision]}})

    versions = await _history(tmp_path, respond).versions(_CURRENT)

    assert versions == (_EARLIEST, _MIDDLE, _CURRENT)
    assert api_pages == [1, 2]
    cache = tmp_path / ".cache" / _CURRENT / "art" / "windows-version-history.txt"
    assert cache.read_text(encoding="utf-8") == f"{_EARLIEST}\n{_MIDDLE}\n{_CURRENT}\n"
    assert "OpenBachelorS" not in cache.read_text(encoding="utf-8")
    assert "oldest" not in cache.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_history_cache_avoids_repeating_network_requests(tmp_path: Path, caplog):
    requests = 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if request.url.host == "api.github.test":
            return httpx.Response(200, json=[{"sha": "current-revision"}])
        return httpx.Response(200, json={"version": {"resVersion": _CURRENT}})

    history = _history(tmp_path, respond)
    with caplog.at_level(logging.INFO):
        assert await history.versions(_CURRENT) == (_CURRENT,)
        assert await history.versions(_CURRENT) == (_CURRENT,)
    assert requests == 2
    outcomes = [
        record
        for record in caplog.records
        if getattr(record, "action", None) == "list"
        and getattr(record, "status", None) in {"done", "cached"}
    ]
    assert [record.status for record in outcomes] == ["done", "cached"]
    assert outcomes[-1].res_version == _CURRENT
    assert outcomes[-1].resource == "windows-version-history"
    assert (outcomes[-1].current, outcomes[-1].total) == (1, 1)
    assert outcomes[-1].elapsed_ms >= 0


@pytest.mark.asyncio
async def test_historical_raw_downloads_have_bounded_concurrency(tmp_path: Path):
    active = 0
    maximum = 0
    release = asyncio.Event()
    saturated = asyncio.Event()
    revisions = [f"revision-{index}" for index in range(12)]

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal active, maximum
        if request.url.host == "api.github.test":
            return httpx.Response(200, json=[{"sha": revision} for revision in revisions])
        active += 1
        maximum = max(maximum, active)
        if active == 8:
            saturated.set()
        try:
            await release.wait()
            return httpx.Response(200, json={"version": {"resVersion": _CURRENT}})
        finally:
            active -= 1

    operation = asyncio.create_task(_history(tmp_path, respond).versions(_CURRENT))
    await asyncio.wait_for(saturated.wait(), timeout=2)
    assert maximum == 8
    release.set()
    assert await asyncio.wait_for(operation, timeout=2) == (_CURRENT,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_payload", "message"),
    [
        ({"version": {"clientVersion": "2.5.01"}}, "does not contain a resVersion"),
        ({"version": {"resVersion": "not-a-version"}}, "malformed Windows resVersion"),
        ({"version": {"resVersion": "26-02-31-00-00-00_abcdef"}}, "malformed.*timestamp"),
    ],
)
async def test_malformed_historical_version_fails_without_skipping(
    tmp_path: Path,
    raw_payload: object,
    message: str,
):
    async def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.test":
            return httpx.Response(200, json=[{"sha": "bad-revision"}])
        return httpx.Response(200, json=raw_payload)

    with pytest.raises((TypeError, ValueError), match=message):
        await _history(tmp_path, respond).versions(_CURRENT)


@pytest.mark.asyncio
async def test_non_chronological_history_fails(tmp_path: Path):
    raw_versions = {"newer": _MIDDLE, "older": _CURRENT}

    async def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.test":
            return httpx.Response(200, json=[{"sha": "newer"}, {"sha": "older"}])
        revision = request.url.path.split("/")[3]
        return httpx.Response(200, json={"version": {"resVersion": raw_versions[revision]}})

    with pytest.raises(ValueError, match="chronological order"):
        await _history(tmp_path, respond).versions(_CURRENT)


@pytest.mark.asyncio
async def test_malformed_commit_page_fails_without_skipping(tmp_path: Path):
    async def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"not_sha": "missing"}])

    with pytest.raises(TypeError, match="has no revision"):
        await _history(tmp_path, respond).versions(_CURRENT)
