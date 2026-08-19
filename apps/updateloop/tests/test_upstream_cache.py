import asyncio
import os
from pathlib import Path, PurePosixPath

import pytest

from arkwaifu_updateloop.upstream import UpstreamCache
from arkwaifu_updateloop.upstream import cache as cache_module


def test_extended_windows_paths_are_canonicalized_for_containment_checks():
    class ExtendedPath:
        @staticmethod
        def resolve() -> str:
            return r"\\?\E:\cache\entry"

    assert cache_module._canonical_path(ExtendedPath()) == os.path.normcase(r"E:\cache\entry")


@pytest.mark.asyncio
async def test_file_cache_validates_hits_and_replaces_corruption(tmp_path: Path):
    cache = UpstreamCache(tmp_path / ".cache")
    produced = 0

    async def produce(destination: Path) -> None:
        nonlocal produced
        produced += 1
        destination.write_text("valid", encoding="utf-8")

    def validate(path: Path) -> None:
        if path.read_text(encoding="utf-8") != "valid":
            raise ValueError("corrupt")

    first = await cache.file("version-1", PurePosixPath("artwork", "bundle.dat"), produce, validate)
    second = await cache.file(
        "version-1", PurePosixPath("artwork", "bundle.dat"), produce, validate
    )

    assert first == second
    assert produced == 1

    first.write_text("broken", encoding="utf-8")
    await cache.file("version-1", PurePosixPath("artwork", "bundle.dat"), produce, validate)

    assert produced == 2
    assert first.read_text(encoding="utf-8") == "valid"


@pytest.mark.asyncio
async def test_directory_cache_exposes_only_completed_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cache = UpstreamCache(tmp_path / ".cache")
    produced = 0
    replacements = 0
    real_replace = os.replace

    def replace_after_transient_windows_locks(source: Path, destination: Path) -> None:
        nonlocal replacements
        replacements += 1
        if replacements <= 2:
            raise PermissionError("temporarily scanned")
        real_replace(source, destination)

    monkeypatch.setattr(
        "arkwaifu_updateloop.upstream.cache.os.replace",
        replace_after_transient_windows_locks,
    )

    async def produce(destination: Path) -> None:
        nonlocal produced
        produced += 1
        (destination / "value.txt").write_text(str(produced), encoding="utf-8")

    first = await cache.directory(
        "version-1", PurePosixPath("artwork", "extracted"), "fingerprint-1", produce
    )
    second = await cache.directory(
        "version-1", PurePosixPath("artwork", "extracted"), "fingerprint-1", produce
    )
    replaced = await cache.directory(
        "version-1", PurePosixPath("artwork", "extracted"), "fingerprint-2", produce
    )

    assert first.path == second.path == replaced.path
    assert first.value is None
    assert second.value is None
    assert replaced.value is None
    assert produced == 2
    assert replacements == 5
    assert (replaced.path / "value.txt").read_text(encoding="utf-8") == "2"


@pytest.mark.asyncio
async def test_directory_cache_rebuilds_when_completed_content_is_corrupt(tmp_path: Path):
    cache = UpstreamCache(tmp_path / ".cache")
    produced = 0

    async def produce(destination: Path) -> None:
        nonlocal produced
        produced += 1
        (destination / "value.txt").write_text("valid", encoding="utf-8")

    def validate(destination: Path) -> str:
        if (destination / "value.txt").read_text(encoding="utf-8") != "valid":
            raise ValueError("corrupt")
        return "validated"

    directory = await cache.directory(
        "version-1",
        PurePosixPath("artwork", "processed"),
        "fingerprint",
        produce,
        validate,
    )
    (directory.path / "value.txt").write_text("broken", encoding="utf-8")

    rebuilt = await cache.directory(
        "version-1",
        PurePosixPath("artwork", "processed"),
        "fingerprint",
        produce,
        validate,
    )

    assert rebuilt.path == directory.path
    assert directory.value == "validated"
    assert rebuilt.value == "validated"
    assert produced == 2
    assert (rebuilt.path / "value.txt").read_text(encoding="utf-8") == "valid"


@pytest.mark.asyncio
async def test_directory_cache_replaces_a_file_at_the_cache_path(tmp_path: Path):
    cache = UpstreamCache(tmp_path / ".cache")
    destination = cache.root / "version-1/artwork/processed"
    destination.parent.mkdir(parents=True)
    destination.write_text("corrupt", encoding="utf-8")

    async def produce(path: Path) -> None:
        (path / "value.txt").write_text("valid", encoding="utf-8")

    rebuilt = await cache.directory(
        "version-1",
        PurePosixPath("artwork", "processed"),
        "fingerprint",
        produce,
    )

    assert (rebuilt.path / "value.txt").read_text(encoding="utf-8") == "valid"


@pytest.mark.asyncio
async def test_directory_validator_observes_the_promoted_stable_path(tmp_path: Path):
    cache = UpstreamCache(tmp_path / ".cache")

    async def produce(destination: Path) -> None:
        (destination / "value.txt").write_text("valid", encoding="utf-8")

    def validate(destination: Path) -> Path:
        assert (destination / "value.txt").read_text(encoding="utf-8") == "valid"
        return destination.resolve()

    cached = await cache.directory(
        "version-1",
        PurePosixPath("artwork", "rendered"),
        "fingerprint",
        produce,
        validate,
    )

    assert cached.value == cached.path.resolve()


@pytest.mark.asyncio
async def test_failed_directory_validation_restores_the_previous_entry(tmp_path: Path):
    cache = UpstreamCache(tmp_path / ".cache")

    async def produce_valid(destination: Path) -> None:
        (destination / "value.txt").write_text("previous", encoding="utf-8")

    def validate_valid(destination: Path) -> str:
        return (destination / "value.txt").read_text(encoding="utf-8")

    previous = await cache.directory(
        "version-1",
        PurePosixPath("artwork", "rendered"),
        "old-fingerprint",
        produce_valid,
        validate_valid,
    )

    async def produce_invalid(destination: Path) -> None:
        (destination / "value.txt").write_text("invalid", encoding="utf-8")

    def reject(_destination: Path) -> None:
        raise ValueError("candidate is invalid")

    with pytest.raises(ValueError, match="candidate is invalid"):
        await cache.directory(
            "version-1",
            PurePosixPath("artwork", "rendered"),
            "new-fingerprint",
            produce_invalid,
            reject,
        )

    assert (previous.path / "value.txt").read_text(encoding="utf-8") == "previous"


@pytest.mark.asyncio
async def test_same_directory_key_runs_only_one_concurrent_producer(tmp_path: Path):
    cache = UpstreamCache(tmp_path / ".cache")
    producer_started = asyncio.Event()
    producer_gate = asyncio.Event()
    produced = 0

    async def produce(destination: Path) -> None:
        nonlocal produced
        produced += 1
        producer_started.set()
        await producer_gate.wait()
        (destination / "value.txt").write_text("valid", encoding="utf-8")

    def validate(destination: Path) -> str:
        return (destination / "value.txt").read_text(encoding="utf-8")

    first = asyncio.create_task(
        cache.directory(
            "version-1",
            PurePosixPath("artwork", "extracted"),
            "fingerprint",
            produce,
            validate,
        )
    )
    await asyncio.wait_for(producer_started.wait(), timeout=2)
    second = asyncio.create_task(
        cache.directory(
            "version-1",
            PurePosixPath("artwork", "extracted"),
            "fingerprint",
            produce,
            validate,
        )
    )
    await asyncio.sleep(0)

    assert produced == 1
    assert not second.done()

    producer_gate.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert produced == 1
    assert first_result.path == second_result.path
    assert first_result.value == second_result.value == "valid"


@pytest.mark.asyncio
async def test_cancelling_file_materialization_drains_the_producer_before_cleanup(
    tmp_path: Path,
):
    cache = UpstreamCache(tmp_path / ".cache")
    producer_started = asyncio.Event()
    producer_gate = asyncio.Event()
    temporary: Path | None = None

    async def gated_producer(destination: Path) -> None:
        nonlocal temporary
        temporary = destination
        destination.write_bytes(b"partial")
        producer_started.set()
        await producer_gate.wait()
        destination.write_bytes(b"complete")

    def validate(path: Path) -> None:
        assert path.read_bytes() == b"complete"

    materialization = asyncio.create_task(
        cache.file(
            "version-1",
            PurePosixPath("artwork", "bundle.dat"),
            gated_producer,
            validate,
        )
    )
    await asyncio.wait_for(producer_started.wait(), timeout=2)
    assert temporary is not None

    materialization.cancel()
    await asyncio.sleep(0)
    assert not materialization.done()
    assert temporary.exists()

    materialization.cancel()
    await asyncio.sleep(0)
    assert not materialization.done()
    assert temporary.exists()

    producer_gate.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(materialization, timeout=2)

    assert not temporary.exists()

    retried = False

    async def retry_producer(destination: Path) -> None:
        nonlocal retried
        retried = True
        destination.write_bytes(b"complete")

    result = await asyncio.wait_for(
        cache.file(
            "version-1",
            PurePosixPath("artwork", "bundle.dat"),
            retry_producer,
            validate,
        ),
        timeout=2,
    )
    assert retried
    assert result.read_bytes() == b"complete"


@pytest.mark.asyncio
async def test_cancelling_cross_process_lock_wait_does_not_leak_the_lock(tmp_path: Path):
    root = tmp_path / ".cache"
    first_cache = UpstreamCache(root)
    waiting_cache = UpstreamCache(root)
    final_cache = UpstreamCache(root)
    destination = first_cache._path("version-1", PurePosixPath("artwork", "bundle.dat"))

    async def produce(path: Path) -> None:
        path.write_bytes(b"valid")

    def validate(path: Path) -> None:
        assert path.read_bytes() == b"valid"

    async with first_cache._locked(destination):
        waiting = asyncio.create_task(
            waiting_cache.file(
                "version-1",
                PurePosixPath("artwork", "bundle.dat"),
                produce,
                validate,
            )
        )
        await asyncio.sleep(0.1)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(waiting, timeout=1)

    result = await asyncio.wait_for(
        final_cache.file(
            "version-1",
            PurePosixPath("artwork", "bundle.dat"),
            produce,
            validate,
        ),
        timeout=1,
    )
    assert result.read_bytes() == b"valid"


@pytest.mark.asyncio
async def test_cache_rejects_unsafe_version_and_relative_paths(tmp_path: Path):
    cache = UpstreamCache(tmp_path / ".cache")

    async def produce(destination: Path) -> None:
        destination.write_bytes(b"value")

    with pytest.raises(ValueError, match="unsafe upstream version"):
        await cache.file("../escape", PurePosixPath("value"), produce, lambda _path: None)

    with pytest.raises(ValueError, match="unsafe relative cache path"):
        await cache.file("version", PurePosixPath("..", "value"), produce, lambda _path: None)
