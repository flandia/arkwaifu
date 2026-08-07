import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from main import (
    EXTRACTOR_TASKS_PER_WORKER,
    mono_behaviour_name,
    normalize_container_path,
    unpack_assets,
)


class MissingScript:
    def read(self):
        raise FileNotFoundError("shared MonoScript CAB is not in this bundle")


class ExtractorIntegrationHelpersTest(unittest.TestCase):
    def test_dyn_container_is_mapped_to_scanner_root(self):
        self.assertEqual(
            normalize_container_path(Path("dyn/avg/characters/example.prefab")),
            Path("assets/torappu/dynamicassets/avg/characters/example.prefab"),
        )

    def test_sprite_hub_name_survives_missing_monoscript(self):
        obj = SimpleNamespace(
            m_Script=MissingScript(),
            object_reader=SimpleNamespace(path_id=123),
        )
        self.assertEqual(
            mono_behaviour_name(obj, {"m_Script": {}, "spriteGroups": []}),
            "AVGCharacterSpriteHubGroup",
        )

    def test_unknown_missing_monoscript_gets_stable_name(self):
        obj = SimpleNamespace(
            m_Script=MissingScript(),
            object_reader=SimpleNamespace(path_id=123),
        )
        self.assertEqual(
            mono_behaviour_name(obj, {"m_Script": {}}),
            "MonoBehaviour_123",
        )

    def test_directory_mode_reports_worker_failures(self):
        class FailingFuture:
            def result(self):
                raise RuntimeError("worker failed")

        class RecordingExecutor:
            tasks_per_child = None

            def __init__(self, max_workers=None, max_tasks_per_child=None):
                self.__class__.tasks_per_child = max_tasks_per_child

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def submit(self, *args):
                return FailingFuture()

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            (source / "bundle.ab").touch()

            with patch("main.ProcessPoolExecutor", RecordingExecutor):
                with self.assertRaisesRegex(RuntimeError, "worker failed"):
                    unpack_assets(source, Path(tmp) / "output", workers=1)

        self.assertEqual(
            RecordingExecutor.tasks_per_child,
            EXTRACTOR_TASKS_PER_WORKER,
        )


if __name__ == "__main__":
    unittest.main()
