import unittest
from pathlib import Path
from types import SimpleNamespace

from main import mono_behaviour_name, normalize_container_path


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


if __name__ == "__main__":
    unittest.main()
