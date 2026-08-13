"""Keep fetched and processed upstream data reusable between update runs.

Files and directories are produced at temporary paths, validated, and then
moved into place. In-process and file-system locks keep two workers or updater
processes from materializing the same entry at once. A completed entry is never
served merely because it exists: files pass their validator, and directories
must also carry the expected format fingerprint.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import shutil
import threading
import time
import uuid
import zipfile
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import BinaryIO

from ..asyncio_tools import await_owned

_VERSION_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
_MARKER = ".arkwaifu-cache.json"

FileProducer = Callable[[Path], Awaitable[None]]
FileValidator = Callable[[Path], object]
DirectoryProducer = Callable[[Path], Awaitable[object | None] | object | None]
DirectoryValidator = Callable[[Path], object]
CacheHitObserver = Callable[[], None]
_CACHE_ERRORS = (OSError, ValueError, TypeError, KeyError, EOFError, zipfile.BadZipFile)


class _LockAcquisitionCancelled(Exception):
    """Stop a blocking file-lock acquisition after its asyncio task is cancelled."""


@dataclass(frozen=True, slots=True)
class CachedDirectory:
    """Return a completed cache directory and the validator's decoded value."""

    path: Path
    value: object | None


def _acquire_file_lock(path: Path, cancelled: threading.Event | None = None) -> BinaryIO:
    """Acquire one cross-process cache lock without blocking cancellation forever."""

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if os.name == "nt":
        import msvcrt

        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        while True:
            if cancelled is not None and cancelled.is_set():
                handle.close()
                raise _LockAcquisitionCancelled
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return handle
            except OSError:
                if cancelled is None:
                    time.sleep(0.05)
                else:
                    cancelled.wait(0.05)
    else:
        import fcntl

        while True:
            if cancelled is not None and cancelled.is_set():
                handle.close()
                raise _LockAcquisitionCancelled
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return handle
            except BlockingIOError:
                if cancelled is None:
                    time.sleep(0.05)
                else:
                    cancelled.wait(0.05)


def _release_file_lock(handle: BinaryIO) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


async def _release_file_lock_safely(handle: BinaryIO) -> None:
    """Release a lock even when the awaiting updater task is cancelled."""

    await await_owned(asyncio.to_thread(_release_file_lock, handle))


def _remove_cache_entry(path: Path) -> None:
    """Remove a cache entry, retrying transient Windows sharing violations."""

    for attempt in range(20):
        try:
            if path.is_symlink() or not path.is_dir():
                path.unlink()
            else:
                shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(min(0.05 * (2**attempt), 1.0))


def _canonical_path(path: Path) -> str:
    value = os.path.normcase(str(path.resolve()))
    return value.removeprefix("\\\\?\\")


class UpstreamCache:
    """Store validated upstream files and completed trees under one version.

    The cache materializes and replaces entries. Callers define each producer, validator, and format fingerprint.
    """

    def __init__(self, root: Path) -> None:
        """Confine all cache entries below ``root``."""
        self._root = root.resolve()
        self._locks: dict[Path, asyncio.Lock] = {}

    @property
    def root(self) -> Path:
        """Return the absolute root below which all cache entries are confined."""

        return self._root

    async def file(
        self,
        version: str,
        relative: PurePath,
        producer: FileProducer,
        validator: FileValidator,
        *,
        on_hit: CacheHitObserver | None = None,
    ) -> Path:
        """Get or produce one validated file.

        A corrupt hit is removed. Newly produced content gets one more attempt
        when validation fails, then replaces the destination only after it is
        known to be usable. ``on_hit`` observes only a validated reuse, allowing
        callers to report caching without guessing from path existence.
        """

        destination = self._path(version, relative)
        async with self._locked(destination):
            if destination.is_file():
                try:
                    await await_owned(asyncio.to_thread(validator, destination))
                    if on_hit is not None:
                        on_hit()
                    return destination
                except _CACHE_ERRORS:
                    destination.unlink(missing_ok=True)

            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
            try:
                for attempt in range(2):
                    await await_owned(producer(temporary))
                    try:
                        await await_owned(asyncio.to_thread(validator, temporary))
                        break
                    except _CACHE_ERRORS:
                        temporary.unlink(missing_ok=True)
                        if attempt == 1:
                            raise
                await self._replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
            return destination

    async def directory(
        self,
        version: str,
        relative: PurePath,
        fingerprint: str,
        producer: DirectoryProducer,
        validator: DirectoryValidator | None = None,
        *,
        on_hit: CacheHitObserver | None = None,
    ) -> CachedDirectory:
        """Get or produce one completed directory.

        ``fingerprint`` identifies the producer's on-disk format and inputs.
        Replacement keeps the previous completed tree as a temporary backup so
        failed validation cannot destroy a usable cache entry. ``on_hit`` runs
        only after the marker and optional validator both accept an existing tree.
        """

        destination = self._path(version, relative)
        async with self._locked(destination):
            marker = destination / _MARKER
            if self._marker_matches(marker, fingerprint):
                try:
                    value = (
                        await await_owned(asyncio.to_thread(validator, destination))
                        if validator is not None
                        else None
                    )
                    if on_hit is not None:
                        on_hit()
                    return CachedDirectory(destination, value)
                except _CACHE_ERRORS:
                    pass

            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
            backup = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.backup")
            try:
                temporary.mkdir()
                value = producer(temporary)
                if inspect.isawaitable(value):
                    value = await await_owned(value)
                (temporary / _MARKER).write_text(
                    json.dumps({"fingerprint": fingerprint}, separators=(",", ":")),
                    encoding="utf-8",
                )
                if destination.exists():
                    await self._replace(destination, backup)
                try:
                    await self._replace(temporary, destination)
                except BaseException:
                    if backup.exists() and not destination.exists():
                        await self._replace(backup, destination)
                    raise
                try:
                    if validator is not None:
                        value = await await_owned(asyncio.to_thread(validator, destination))
                except BaseException:
                    if destination.exists():
                        await await_owned(asyncio.to_thread(_remove_cache_entry, destination))
                    if backup.exists():
                        await self._replace(backup, destination)
                    raise
                if backup.exists():
                    await await_owned(asyncio.to_thread(_remove_cache_entry, backup))
                return CachedDirectory(destination, value)
            finally:
                if temporary.exists():
                    await await_owned(asyncio.to_thread(_remove_cache_entry, temporary))

    def _path(self, version: str, relative: PurePath) -> Path:
        """Resolve an entry while confining it below ``root/version``."""

        if not _VERSION_COMPONENT.fullmatch(version):
            raise ValueError(f"unsafe upstream version for cache path: {version!r}")
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise ValueError(f"unsafe relative cache path: {relative}")
        destination = self._root / version / Path(*relative.parts)
        root = _canonical_path(self._root)
        candidate = _canonical_path(destination)
        try:
            inside_root = os.path.commonpath((root, candidate)) == root
        except ValueError:
            inside_root = False
        if not inside_root:
            raise ValueError(f"unsafe relative cache path: {relative}")
        return destination

    @staticmethod
    async def _replace(source: Path, destination: Path) -> None:
        """Move one cache entry into place, tolerating Windows file scanners."""

        for attempt in range(20):
            try:
                os.replace(source, destination)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                await asyncio.sleep(min(0.05 * (2**attempt), 1.0))

    @asynccontextmanager
    async def _locked(self, destination: Path):
        """Serialize materialization in this loop and across updater processes."""

        local_lock = self._locks.setdefault(destination, asyncio.Lock())
        async with local_lock:
            cancelled = threading.Event()
            acquisition = asyncio.create_task(
                asyncio.to_thread(
                    _acquire_file_lock,
                    destination.with_name(f".{destination.name}.lock"),
                    cancelled,
                )
            )
            try:
                handle = await asyncio.shield(acquisition)
            except asyncio.CancelledError as cancellation:
                cancelled.set()
                while True:
                    try:
                        handle = await asyncio.shield(acquisition)
                        break
                    except asyncio.CancelledError:
                        continue
                    except _LockAcquisitionCancelled as error:
                        raise cancellation from error
                    except BaseException as error:
                        raise cancellation from error
                await _release_file_lock_safely(handle)
                raise
            try:
                yield
            finally:
                await _release_file_lock_safely(handle)

    @staticmethod
    def _marker_matches(marker: Path, fingerprint: str) -> bool:
        """Return whether a directory was completed by the expected producer."""

        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
        except OSError, ValueError, TypeError:
            return False
        return isinstance(payload, dict) and payload.get("fingerprint") == fingerprint
