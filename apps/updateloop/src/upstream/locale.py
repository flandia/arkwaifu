"""Pull and parse story and gallery data for every game server.

ArknightsAssets publishes all servers in one branch archive. A default update
downloads that snapshot once, verifies each locale's embedded ``versionId``,
and extracts only the tables and story files understood by the parsers. The
selected files are placed under the same normalized asset prefix used by the
previous updater.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import httpx

from ..asyncio_tools import await_owned
from ..domain import LocaleManifest, LocaleUnit
from ..local_path import resolve_local_path, safe_relative_path
from ..locale import parse_galleries, parse_story_groups
from .cache import UpstreamCache

_REPOSITORY = "ArknightsAssets/ArknightsGamedata"
_BRANCH = "master"
_SERVER_DIRECTORIES = {"CN": "cn", "EN": "en", "JP": "jp", "KR": "kr", "TW": "tw"}
# These repositories record periodic snapshots rather than every resVersion,
# so files added and removed between snapshots may still be unrecoverable.
_STORY_HISTORY_SOURCES = {
    "CN": (
        ("https://github.com/ArknightsAssets/ArknightsGamedata.git", _BRANCH, "cn"),
        ("https://github.com/Kengxxiao/ArknightsGameData.git", "master", "zh_CN"),
    ),
    "EN": (
        ("https://github.com/ArknightsAssets/ArknightsGamedata.git", _BRANCH, "en"),
        ("https://github.com/Kengxxiao/ArknightsGameData_YoStar.git", "main", "en_US"),
        ("https://github.com/Kengxxiao/ArknightsGameData.git", "master", "en_US"),
    ),
    "JP": (
        ("https://github.com/ArknightsAssets/ArknightsGamedata.git", _BRANCH, "jp"),
        ("https://github.com/Kengxxiao/ArknightsGameData_YoStar.git", "main", "ja_JP"),
        ("https://github.com/Kengxxiao/ArknightsGameData.git", "master", "ja_JP"),
    ),
    "KR": (
        ("https://github.com/ArknightsAssets/ArknightsGamedata.git", _BRANCH, "kr"),
        ("https://github.com/Kengxxiao/ArknightsGameData_YoStar.git", "main", "ko_KR"),
        ("https://github.com/Kengxxiao/ArknightsGameData.git", "master", "ko_KR"),
    ),
    "TW": (
        ("https://github.com/ArknightsAssets/ArknightsGamedata.git", _BRANCH, "tw"),
        ("https://github.com/aelurum/ArknightsGameData.git", "master_v2", "zh_TW"),
    ),
}
_SELECTED_PATHS = {
    "gamedata/excel/activity_table.json",
    "gamedata/excel/replicate_table.json",
    "gamedata/excel/retro_table.json",
    "gamedata/excel/roguelike_topic_table.json",
    "gamedata/excel/sandbox_perm_table.json",
    "gamedata/excel/stage_table.json",
    "gamedata/excel/story_review_meta_table.json",
    "gamedata/excel/story_review_table.json",
}
# Bump this when the selected inputs or extracted directory layout changes;
# resVersion identifies upstream content, not the local extraction recipe.
_LOCALE_EXTRACTION_CACHE_FORMAT = "5"
_RAW_CONTENT_ACCEPT = "application/vnd.github.raw+json"

_ASSET_PREFIX = Path("assets/torappu/dynamicassets")
_DATA_ROOT = _ASSET_PREFIX / "gamedata"

_ARCHIVE_CACHE_NAMESPACE = "game-data"
_ARCHIVE_CACHE_PATH = PurePosixPath("archive.zip")


class _SnapshotVersionMismatch(RuntimeError):
    def __init__(self, unit: LocaleUnit, expected: str, embedded: str) -> None:
        self.unit = unit
        self.expected = expected
        self.embedded = embedded
        super().__init__(
            f"{unit} cached master snapshot has version {embedded}, expected {expected}"
        )


def _parse_manifest(
    unit: LocaleUnit,
    upstream_version: str,
    data_root: Path,
) -> LocaleManifest:
    """Parse the selected files for one locale into publication records."""

    return LocaleManifest(
        unit=unit,
        upstream_version=upstream_version,
        story_groups=parse_story_groups(data_root),
        galleries=parse_galleries(data_root),
    )


def _missing_story_paths(data_root: Path) -> tuple[PurePosixPath, ...]:
    """Return indexed story text paths absent from the current snapshot."""

    with (data_root / _DATA_ROOT / "excel/story_review_table.json").open(
        encoding="utf-8"
    ) as handle:
        review_table = json.load(handle)
    with (data_root / _DATA_ROOT / "excel/roguelike_topic_table.json").open(
        encoding="utf-8"
    ) as handle:
        roguelike_table = json.load(handle)
    with (data_root / _DATA_ROOT / "excel/story_review_meta_table.json").open(
        encoding="utf-8"
    ) as handle:
        review_meta = json.load(handle)
    with (data_root / _DATA_ROOT / "excel/sandbox_perm_table.json").open(
        encoding="utf-8"
    ) as handle:
        sandbox_table = json.load(handle)

    story_names = []
    for group in _json_values(review_table):
        if not isinstance(group, dict):
            continue
        for story in _json_values(group.get("infoUnlockDatas")):
            if isinstance(story, dict):
                story_names.append(story.get("storyTxt"))
    details = roguelike_table.get("details") if isinstance(roguelike_table, dict) else None
    for detail in _json_values(details):
        archive = detail.get("archiveComp") if isinstance(detail, dict) else None
        endbook_group = archive.get("endbook") if isinstance(archive, dict) else None
        endbooks = endbook_group.get("endbook") if isinstance(endbook_group, dict) else None
        for ending in _json_values(endbooks):
            if isinstance(ending, dict):
                story_names.append(ending.get("avgId"))
    sandbox_details = sandbox_table.get("detail") if isinstance(sandbox_table, dict) else None
    for template in _json_values(sandbox_details):
        for detail in _json_values(template):
            quests = detail.get("archiveQuestData") if isinstance(detail, dict) else None
            for quest in _json_values(quests):
                stories = quest.get("avgDataList") if isinstance(quest, dict) else None
                for story in _json_values(stories):
                    if isinstance(story, dict):
                        story_names.append(story.get("avgId"))
    archive_data = review_meta.get("actArchiveResData") if isinstance(review_meta, dict) else None
    avgs = archive_data.get("avgs") if isinstance(archive_data, dict) else None
    for avg in _json_values(avgs):
        story_name = avg.get("contentPath") if isinstance(avg, dict) else None
        if isinstance(story_name, str) and story_name.lower().startswith(
            "obt/roguelike/ro1/level_rogue1_ending_"
        ):
            story_names.append(story_name)

    missing: dict[PurePosixPath, None] = {}
    for story_name in story_names:
        if not isinstance(story_name, str) or not story_name:
            continue
        relative = safe_relative_path(story_name, context="historical story path")
        if relative.suffix.lower() == ".txt":
            relative = relative.with_suffix("")
        path = PurePosixPath(f"gamedata/story/{relative.as_posix()}.txt")
        path = PurePosixPath(path.as_posix().lower())
        local_path = resolve_local_path(
            data_root / _ASSET_PREFIX,
            path,
            context="historical story path",
        )
        if not local_path.is_file():
            missing[path] = None
    return tuple(missing)


def _json_values(value: object) -> tuple[object, ...]:
    if isinstance(value, dict):
        return tuple(value.values())
    if isinstance(value, list):
        return tuple(value)
    return ()


def _write_story_text(data_root: Path, path: PurePosixPath, content: bytes) -> None:
    output = resolve_local_path(
        data_root / _ASSET_PREFIX,
        path,
        context="historical story path",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)


def _version_id(payload: object, context: str) -> str:
    """Read a non-empty resource version from ``hot_update_list.json``."""

    version = payload.get("versionId") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not version:
        raise TypeError(f"{context} does not contain a versionId")
    return version


class LiveLocaleBuilder:
    """Resolve a snapshot and parse its available story and gallery data.

    A repository commit is not part of the publication identity. The locale's
    embedded resource version is the only version recorded by the updater. One
    builder belongs to one update run and owns the all-server branch snapshot
    shared by every requested locale in that run.
    """

    def __init__(
        self,
        *,
        github_api_url: str = "https://api.github.com",
        github_token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        cache: UpstreamCache | None = None,
    ) -> None:
        self._api_url = github_api_url.rstrip("/")
        self._token = github_token or None
        self._transport = transport
        self._cache = cache
        self._detected_versions: dict[LocaleUnit, str] = {}
        self._archive_task: asyncio.Task[Path] | None = None
        self._archive_directory: tempfile.TemporaryDirectory[str] | None = None
        self._history_directory: tempfile.TemporaryDirectory[str] | None = None
        self._history_clone_tasks: dict[tuple[str, str], asyncio.Task[Path]] = {}
        self._history_repository_locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._closed = False

    async def detect_version(self, unit: LocaleUnit) -> str:
        """Get the current resource version published for one server."""

        self._ensure_open()
        async with self._client() as client:
            version = await self._branch_version(client, unit)
        self._detected_versions[unit] = version
        return version

    async def build(
        self,
        unit: LocaleUnit,
        upstream_version: str,
        _active_version: str | None,
        _force: bool,
    ) -> LocaleManifest:
        """Download one consistent snapshot and build the requested locale."""

        self._ensure_open()
        detected = self._detected_versions.get(unit)
        if detected is not None and detected != upstream_version:
            raise ValueError(f"{unit} was detected at {detected}, cannot build {upstream_version}")
        self._detected_versions.setdefault(unit, upstream_version)
        with tempfile.TemporaryDirectory(prefix=f"arkwaifu-{unit.lower()}-") as temporary:
            root = Path(temporary)
            archive = await self._archive()

            embedded_version = await await_owned(
                asyncio.to_thread(
                    self._archive_version,
                    archive,
                    _SERVER_DIRECTORIES[unit],
                )
            )
            if embedded_version != upstream_version:
                raise RuntimeError(
                    f"{unit} changed from {upstream_version} to "
                    f"{embedded_version} in the downloaded master snapshot"
                )

            if self._cache is None:
                data_root = root / "data"
                await await_owned(
                    asyncio.to_thread(
                        self._extract,
                        archive,
                        data_root,
                        _SERVER_DIRECTORIES[unit],
                    )
                )
                await self._recover_missing_story_texts(unit, data_root)
            else:
                fingerprint = f"{_LOCALE_EXTRACTION_CACHE_FORMAT}:{unit}:{upstream_version}"

                async def materialize(destination: Path) -> None:
                    await await_owned(
                        asyncio.to_thread(
                            self._extract,
                            archive,
                            destination,
                            _SERVER_DIRECTORIES[unit],
                        )
                    )
                    await self._recover_missing_story_texts(unit, destination)

                cached_locale = await self._cache.directory(
                    upstream_version,
                    PurePosixPath("game-data", unit, "extracted"),
                    fingerprint,
                    materialize,
                    lambda path: _parse_manifest(unit, upstream_version, path),
                )
                if not isinstance(cached_locale.value, LocaleManifest):
                    raise TypeError(f"cached {unit} locale has no manifest: {cached_locale.path}")
                return cached_locale.value
            return await await_owned(
                asyncio.to_thread(_parse_manifest, unit, upstream_version, data_root)
            )

    async def _recover_missing_story_texts(
        self,
        unit: LocaleUnit,
        data_root: Path,
    ) -> None:
        """Fill missing story paths with the latest copy in the source order."""

        missing = await await_owned(asyncio.to_thread(_missing_story_paths, data_root))
        if not missing:
            return
        unresolved = dict.fromkeys(missing)
        for repository_url, branch, root in _STORY_HISTORY_SOURCES[unit]:
            clone = await self._history_repository(repository_url, branch)
            lock = self._history_repository_locks.setdefault(
                (repository_url, branch),
                asyncio.Lock(),
            )
            async with lock:
                for path in tuple(unresolved):
                    repository_path = PurePosixPath(root) / path
                    content = await await_owned(
                        asyncio.to_thread(
                            self._latest_historical_story,
                            clone,
                            repository_path,
                        )
                    )
                    if content is None:
                        continue
                    await await_owned(
                        asyncio.to_thread(_write_story_text, data_root, path, content)
                    )
                    del unresolved[path]
            if not unresolved:
                return

    async def _history_repository(self, repository_url: str, branch: str) -> Path:
        """Clone one branch without blobs and share it across locale builds."""

        self._ensure_open()
        key = (repository_url, branch)
        task = self._history_clone_tasks.get(key)
        if task is None:
            destination = self._history_root() / f"repository-{len(self._history_clone_tasks)}"
            task = asyncio.create_task(
                self._clone_history_repository(repository_url, branch, destination),
                name=f"clone-story-history-{len(self._history_clone_tasks)}",
            )
            self._history_clone_tasks[key] = task
        return await asyncio.shield(task)

    def _history_root(self) -> Path:
        """Create the run-scoped clone root on the configured cache drive."""

        if self._history_directory is None:
            parent = self._cache.root if self._cache is not None else None
            if parent is not None:
                parent.mkdir(parents=True, exist_ok=True)
            self._history_directory = tempfile.TemporaryDirectory(
                prefix=".story-history-",
                dir=parent,
            )
        return Path(self._history_directory.name)

    async def _clone_history_repository(
        self,
        repository_url: str,
        branch: str,
        destination: Path,
    ) -> Path:
        await await_owned(
            asyncio.to_thread(
                self._run_git,
                "clone",
                "--quiet",
                "--filter=blob:none",
                "--no-checkout",
                "--single-branch",
                "--no-tags",
                "--branch",
                branch,
                repository_url,
                str(destination),
            )
        )
        return destination

    @classmethod
    def _latest_historical_story(
        cls,
        repository: Path,
        path: PurePosixPath,
    ) -> bytes | None:
        """Read the newest revision which added or modified an exact path."""

        revision = (
            cls._run_git(
                "--literal-pathspecs",
                "-C",
                str(repository),
                "log",
                "-1",
                "--full-history",
                "--no-renames",
                "--diff-filter=AM",
                "--format=%H",
                "--",
                path.as_posix(),
            )
            .decode("ascii")
            .strip()
        )
        if not revision:
            return None
        content = cls._run_git(
            "-C",
            str(repository),
            "cat-file",
            "blob",
            f"{revision}:{path.as_posix()}",
        )
        content.decode("utf-8")
        return content

    @staticmethod
    def _run_git(*arguments: str) -> bytes:
        """Run Git without a shell or an interactive credential prompt."""

        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        try:
            result = subprocess.run(
                ("git", *arguments),
                capture_output=True,
                check=False,
                env=environment,
            )
        except FileNotFoundError as error:
            raise RuntimeError("git is required to recover historical story text") from error
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            message = f"git command failed with exit code {result.returncode}"
            if detail:
                message = f"{message}: {detail}"
            raise RuntimeError(message)
        return result.stdout

    async def _archive(self) -> Path:
        """Get the one all-server branch snapshot owned by this builder."""

        if self._archive_task is None:
            expected_versions = dict(self._detected_versions)
            self._archive_task = asyncio.create_task(
                self._materialize_archive(expected_versions),
                name="download-locale-master",
            )
        task = self._archive_task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            raise
        except _SnapshotVersionMismatch as error:
            if self._archive_task is task:
                self._archive_task = None
            raise RuntimeError(
                f"{error.unit} changed from {error.expected} to "
                f"{error.embedded} in the downloaded master snapshot"
            ) from error
        except BaseException:
            if self._archive_task is task:
                self._archive_task = None
            raise

    async def _materialize_archive(
        self,
        expected_versions: dict[LocaleUnit, str],
    ) -> Path:
        """Materialize one snapshot admitted by every detected locale version."""

        cached_archive = (
            self._cache.root / _ARCHIVE_CACHE_NAMESPACE / Path(*_ARCHIVE_CACHE_PATH.parts)
            if self._cache is not None
            else None
        )

        def validate_archive(path: Path) -> None:
            self._validate_archive(path)
            for unit, expected in expected_versions.items():
                embedded = self._archive_version(path, _SERVER_DIRECTORIES[unit])
                if embedded != expected:
                    mismatch = _SnapshotVersionMismatch(unit, expected, embedded)
                    # A mismatch in the stable destination is a stale cache hit,
                    # which UpstreamCache should evict. A newly downloaded
                    # temporary file represents a branch race and must fail the
                    # run without downloading the same snapshot a second time.
                    if cached_archive is not None and path == cached_archive:
                        raise ValueError(str(mismatch)) from mismatch
                    raise mismatch

        async def download(destination: Path) -> None:
            async with self._client() as client:
                await self._download(client, destination)

        if self._cache is not None:
            return await self._cache.file(
                _ARCHIVE_CACHE_NAMESPACE,
                _ARCHIVE_CACHE_PATH,
                download,
                validate_archive,
            )

        directory = tempfile.TemporaryDirectory(prefix="arkwaifu-gamedata-master-")
        self._archive_directory = directory
        destination = Path(directory.name) / "archive.zip"
        try:
            await download(destination)
            await await_owned(asyncio.to_thread(validate_archive, destination))
            return destination
        except BaseException:
            self._archive_directory = None
            await await_owned(asyncio.to_thread(directory.cleanup))
            raise

    async def aclose(self) -> None:
        """Cancel owned work and release run-scoped archives and clones."""

        if self._closed:
            return
        self._closed = True
        archive_task = self._archive_task
        self._archive_task = None
        history_tasks = tuple(self._history_clone_tasks.values())
        self._history_clone_tasks.clear()
        tasks = (*history_tasks, *((archive_task,) if archive_task is not None else ()))
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        archive_directory = self._archive_directory
        self._archive_directory = None
        history_directory = self._history_directory
        self._history_directory = None
        if history_directory is not None:
            await await_owned(asyncio.to_thread(history_directory.cleanup))
        if archive_directory is not None:
            await await_owned(asyncio.to_thread(archive_directory.cleanup))

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("locale builder is closed")

    def _client(self) -> httpx.AsyncClient:
        """Create a GitHub client with optional authentication for rate limits."""

        headers = {"Accept": "application/vnd.github+json", "User-Agent": "arkwaifu-updateloop"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(120, connect=30),
            follow_redirects=True,
            transport=self._transport,
        )

    async def _branch_version(
        self,
        client: httpx.AsyncClient,
        unit: LocaleUnit,
    ) -> str:
        """Read one server's current version directly from the branch."""

        server = _SERVER_DIRECTORIES[unit]
        response = await client.get(
            f"{self._api_url}/repos/{_REPOSITORY}/contents/{server}/hot_update_list.json",
            params={"ref": _BRANCH},
            headers={"Accept": _RAW_CONTENT_ACCEPT},
        )
        response.raise_for_status()
        return _version_id(response.json(), f"{unit} branch hot_update_list.json")

    async def _download(
        self,
        client: httpx.AsyncClient,
        destination: Path,
    ) -> None:
        """Stream the current all-server branch archive to disk."""

        async with client.stream(
            "GET", f"{self._api_url}/repos/{_REPOSITORY}/zipball/{_BRANCH}"
        ) as response:
            response.raise_for_status()
            with destination.open("wb") as output:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    output.write(chunk)

    @staticmethod
    def _archive_version(path: Path, server_directory: str) -> str:
        """Read exactly one server version from a downloaded branch archive."""

        matches: list[zipfile.ZipInfo] = []
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                member_path = PurePosixPath(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError(f"unsafe game-data archive member: {member.filename}")
                if (
                    not member.is_dir()
                    and len(member_path.parts) == 3
                    and member_path.parts[1] == server_directory
                    and member_path.parts[2] == "hot_update_list.json"
                ):
                    matches.append(member)
            if len(matches) != 1:
                raise ValueError(
                    f"master snapshot must contain exactly one "
                    f"{server_directory}/hot_update_list.json"
                )
            payload = json.loads(archive.read(matches[0]))
        return _version_id(payload, f"{server_directory} archive hot_update_list.json")

    @staticmethod
    def _validate_archive(path: Path) -> None:
        """Ask ZIP to decode every member before the archive enters the cache."""

        with zipfile.ZipFile(path) as archive:
            corrupt = archive.testzip()
        if corrupt is not None:
            raise ValueError(f"corrupt game-data archive member: {corrupt}")

    @staticmethod
    def _extract(
        archive_path: Path,
        destination: Path,
        server_directory: str,
    ) -> None:
        """Extract only the story and gallery inputs for one server.

        GitHub zipballs contain a generated top-level directory. The first path
        component is therefore discarded before the server directory is mapped
        below ``assets/torappu/dynamicassets``.
        """

        prefix = Path("assets/torappu/dynamicassets")
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                path = safe_relative_path(
                    member.orig_filename,
                    context="game-data archive member",
                )
                if len(path.parts) < 3:
                    continue
                if path.parts[1] != server_directory:
                    continue
                relative = PurePosixPath(*path.parts[2:])
                relative_text = relative.as_posix()
                selected = relative_text in _SELECTED_PATHS or relative_text.startswith(
                    "gamedata/story/"
                )
                if not selected:
                    continue
                output = resolve_local_path(
                    destination / prefix,
                    relative,
                    context="game-data archive member",
                )
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, output.open("wb") as target:
                    while chunk := source.read(1024 * 1024):
                        target.write(chunk)
