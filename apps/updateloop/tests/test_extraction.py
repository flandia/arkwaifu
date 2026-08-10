from concurrent.futures import Future
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest

from arkwaifu_updateloop.extraction import unity
from arkwaifu_updateloop.extraction.lz4ak import decompress_lz4ak
from arkwaifu_updateloop.extraction.unity import (
    EXTRACTOR_TASKS_PER_WORKER,
    ExtractionError,
    extract_assets,
    mono_behaviour_name,
    normalize_container_path,
)


class MissingScript:
    def read(self):
        raise FileNotFoundError("shared MonoScript CAB is absent")


def test_dyn_container_is_mapped_to_scanner_root():
    assert normalize_container_path("dyn/avg/characters/example.prefab") == PurePosixPath(
        "assets/torappu/dynamicassets/avg/characters/example.prefab"
    )


def test_sprite_hub_name_survives_missing_monoscript():
    obj = SimpleNamespace(
        m_Script=MissingScript(),
        object_reader=SimpleNamespace(path_id=123),
    )
    assert (
        mono_behaviour_name(obj, {"m_Script": {}, "spriteGroups": []})
        == "AVGCharacterSpriteHubGroup"
    )


def test_generated_summary_name_cannot_escape_extraction_root(tmp_path, monkeypatch):
    destination = tmp_path / "output"
    obj = SimpleNamespace(m_Name="../../../../../../escaped")
    reader = SimpleNamespace(read=lambda: obj)
    environment = SimpleNamespace(container={"dyn/avg/characters/example.prefab": reader})

    monkeypatch.setattr(unity, "patch_unitypy", lambda: None)
    monkeypatch.setattr(unity.UnityPy, "load", lambda _source: environment)

    def export(
        _obj,
        _destination,
        _fallback,
        path_ids,
        _type_tree_ids,
    ):
        path_ids[1] = "sprite.png"

    monkeypatch.setattr(unity, "_export", export)

    with pytest.raises(ValueError, match="unsafe Unity container path"):
        unity._extract_one(Path("bundle.ab"), destination)

    assert not (tmp_path / "escaped.json").exists()
    assert not (tmp_path / "escaped.typetree.json").exists()


def test_lz4ak_literal_only_block():
    assert decompress_lz4ak(b"\x05hello", 5) == b"hello"


def test_lz4ak_big_endian_match_offset():
    assert decompress_lz4ak(bytes.fromhex("c36162630003056263616263"), 24) == b"abc" * 8


def test_directory_mode_recycles_workers_and_reports_failures(tmp_path, monkeypatch):
    class RecordingExecutor:
        tasks_per_child = None

        def __init__(self, max_workers=None, max_tasks_per_child=None):
            del max_workers
            self.__class__.tasks_per_child = max_tasks_per_child

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def submit(self, *args):
            del args
            future = Future()
            future.set_exception(RuntimeError("worker failed"))
            return future

    source = tmp_path / "source"
    source.mkdir()
    (source / "bundle.ab").touch()
    monkeypatch.setattr(unity, "ProcessPoolExecutor", RecordingExecutor)

    with pytest.raises(ExtractionError, match="worker failed"):
        extract_assets([source], tmp_path / "output", workers=2)

    assert RecordingExecutor.tasks_per_child == EXTRACTOR_TASKS_PER_WORKER
