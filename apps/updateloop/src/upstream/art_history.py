"""Discover historical Windows resource versions for a complete art run.

The official client API exposes only the current ``resVersion``.  OpenBachelorS
keeps a secondary, twice-daily ledger of values observed from that API, which
lets a complete run discover older official CDN snapshots.  It is not an
authoritative archive: the caller-supplied current version is therefore always
included and must remain the final version processed.

Repository revisions are transient lookup details.  The persistent cache is a
newline-delimited sequence containing only bare ``resVersion`` values.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx

from .cache import UpstreamCache

_REPOSITORY = "pfyy/OpenBachelorS"
_VERSION_PATH = "conf/version_windows.json"
_PAGE_SIZE = 100
_RAW_CONCURRENCY = 8
_CACHE_PATH = PurePosixPath("art", "windows-version-history.txt")
_VERSION_PATTERN = re.compile(
    r"(?P<year>\d{2})-(?P<month>\d{2})-(?P<day>\d{2})-"
    r"(?P<hour>\d{2})-(?P<minute>\d{2})-(?P<second>\d{2})_"
    r"(?P<revision>[0-9a-f]{6})"
)
_LOGGER = logging.getLogger(__name__)


def _log_history_action(
    version: str,
    status: str,
    *,
    count: int | None = None,
    elapsed_seconds: float | None = None,
) -> None:
    """Emit one structured event for Windows version-history discovery."""

    extra: dict[str, object] = {
        "action": "list",
        "status": status,
        "res_version": version,
        "resource": "windows-version-history",
    }
    if count is not None:
        extra["current"] = count
        extra["total"] = count
    if elapsed_seconds is not None:
        extra["elapsed_ms"] = round(elapsed_seconds * 1000, 3)
    _LOGGER.info("art action", extra=extra)


def _version_key(version: str) -> datetime:
    """Validate one official ``resVersion`` and return its release timestamp."""

    match = _VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(f"malformed Windows resVersion: {version!r}")
    try:
        return datetime(
            2000 + int(match["year"]),
            int(match["month"]),
            int(match["day"]),
            int(match["hour"]),
            int(match["minute"]),
            int(match["second"]),
            tzinfo=UTC,
        )
    except ValueError as error:
        raise ValueError(f"malformed Windows resVersion timestamp: {version!r}") from error


def _validate_versions(versions: tuple[str, ...], current_version: str) -> None:
    """Require a unique chronological sequence ending at the current version."""

    if not versions:
        raise ValueError("Windows resVersion history is empty")
    if len(set(versions)) != len(versions):
        raise ValueError("Windows resVersion history contains duplicates")
    keys = tuple(_version_key(version) for version in versions)
    if any(previous >= following for previous, following in pairwise(keys)):
        raise ValueError("Windows resVersion history is not in chronological order")
    if versions[-1] != current_version:
        raise ValueError(
            f"Windows resVersion history does not end at the current version {current_version!r}"
        )


def _read_versions(path: Path, current_version: str) -> tuple[str, ...]:
    """Decode and validate the metadata-free on-disk history format."""

    content = path.read_text(encoding="utf-8")
    versions = tuple(content.splitlines())
    if content and not content.endswith("\n"):
        raise ValueError("Windows resVersion history must end with a newline")
    _validate_versions(versions, current_version)
    return versions


class LiveWindowsVersionHistory:
    """Resolve the ordered official Windows versions needed by a complete run."""

    def __init__(
        self,
        github_api_url: str,
        github_raw_url: str,
        github_token: str | None,
        cache: UpstreamCache,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_url = github_api_url.rstrip("/")
        self._raw_url = github_raw_url.rstrip("/")
        self._token = github_token
        self._cache = cache
        self._transport = transport

    async def versions(self, current_version: str) -> tuple[str, ...]:
        """Return cached or live history from its earliest entry through current."""

        _version_key(current_version)
        started = time.perf_counter()

        async def materialize(destination: Path) -> None:
            versions = await self._fetch_versions(current_version)
            destination.write_text(
                "".join(f"{version}\n" for version in versions), encoding="utf-8"
            )

        def validate(path: Path) -> None:
            _read_versions(path, current_version)

        cache_hit = False

        def observe_cache_hit() -> None:
            nonlocal cache_hit
            cache_hit = True

        try:
            path = await self._cache.file(
                current_version,
                _CACHE_PATH,
                materialize,
                validate,
                on_hit=observe_cache_hit,
            )
            versions = _read_versions(path, current_version)
        except Exception:
            _log_history_action(
                current_version,
                "failed",
                elapsed_seconds=time.perf_counter() - started,
            )
            raise
        _log_history_action(
            current_version,
            "cached" if cache_hit else "done",
            count=len(versions),
            elapsed_seconds=time.perf_counter() - started,
        )
        return versions

    async def _fetch_versions(self, current_version: str) -> tuple[str, ...]:
        revisions = await self._revisions()
        semaphore = asyncio.Semaphore(_RAW_CONCURRENCY)
        async with self._raw_client() as client:

            async def fetch(revision: str) -> str:
                async with semaphore:
                    return await self._version_at(client, revision)

            newest_first = await asyncio.gather(*(fetch(revision) for revision in revisions))

        ordered = tuple(dict.fromkeys(reversed(newest_first)))
        if current_version not in ordered:
            ordered += (current_version,)
        _validate_versions(ordered, current_version)
        return ordered

    async def _revisions(self) -> tuple[str, ...]:
        """Read every commit page for the ledger, newest first."""

        revisions: dict[str, None] = {}
        page = 1
        async with self._api_client() as client:
            while True:
                response = await client.get(
                    f"{self._api_url}/repos/{_REPOSITORY}/commits",
                    params={
                        "path": _VERSION_PATH,
                        "per_page": _PAGE_SIZE,
                        "page": page,
                    },
                )
                response.raise_for_status()
                try:
                    entries = response.json()
                except json.JSONDecodeError as error:
                    raise ValueError(
                        "GitHub Windows version history response is not JSON"
                    ) from error
                if not isinstance(entries, list):
                    raise TypeError("GitHub Windows version history response is not a list")
                for index, entry in enumerate(entries):
                    revision = entry.get("sha") if isinstance(entry, dict) else None
                    if not isinstance(revision, str) or not revision:
                        raise TypeError(
                            "GitHub Windows version history commit "
                            f"{index} on page {page} has no revision"
                        )
                    revisions.setdefault(revision, None)
                if len(entries) < _PAGE_SIZE:
                    break
                page += 1
        if not revisions:
            raise ValueError("GitHub Windows version history contains no revisions")
        return tuple(revisions)

    async def _version_at(self, client: httpx.AsyncClient, revision: str) -> str:
        """Read one bare ``resVersion`` without forwarding API credentials."""

        response = await client.get(
            f"{self._raw_url}/{_REPOSITORY}/{quote(revision, safe='')}/{_VERSION_PATH}"
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except json.JSONDecodeError as error:
            raise ValueError("historical Windows version file is not JSON") from error
        version_object = payload.get("version") if isinstance(payload, dict) else None
        version = version_object.get("resVersion") if isinstance(version_object, dict) else None
        if not isinstance(version, str):
            raise TypeError("historical Windows version file does not contain a resVersion string")
        _version_key(version)
        return version

    def _api_client(self) -> httpx.AsyncClient:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "arkwaifu-updateloop",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(120, connect=30),
            follow_redirects=True,
            transport=self._transport,
        )

    def _raw_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"User-Agent": "arkwaifu-updateloop"},
            timeout=httpx.Timeout(120, connect=30),
            follow_redirects=True,
            transport=self._transport,
        )
