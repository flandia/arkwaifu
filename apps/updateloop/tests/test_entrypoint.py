import importlib
import sys

from arkwaifu_updateloop import cli


def test_main_module_can_be_imported_without_running_cli(monkeypatch):
    called = False

    def main() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(cli, "main", main)
    sys.modules.pop("arkwaifu_updateloop.__main__", None)
    try:
        importlib.import_module("arkwaifu_updateloop.__main__")
    finally:
        sys.modules.pop("arkwaifu_updateloop.__main__", None)

    assert called is False
