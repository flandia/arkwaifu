import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from arkwaifu_updateloop import MemoryObjectStore, Updater, UpdateRequest, cli
from arkwaifu_updateloop.database import initialize_or_validate


@pytest.mark.parametrize("state", ["current", "changed", "missing", "repair", "invalid"])
async def test_check_database_never_builds_or_publishes(state, tmp_path):
    store = MemoryObjectStore()
    if state != "missing":
        database = tmp_path / "database.sqlite3"
        initialize_or_validate(database)
        with sqlite3.connect(database) as connection:
            connection.execute("INSERT INTO unit_versions VALUES ('CN', 'v1')")
            if state == "repair":
                connection.execute("DROP INDEX story_narrative_image_references_by_asset")
            if state == "invalid":
                connection.execute("PRAGMA user_version=99")
        store.database = database.read_bytes()
    before = store.database
    store.push_database = AsyncMock(side_effect=AssertionError("check must not publish"))
    build = AsyncMock(side_effect=AssertionError("check must not build"))
    requests = [UpdateRequest("CN", "v2" if state == "changed" else "v1", build)]
    if state == "invalid":
        with pytest.raises(ValueError, match="schema version"):
            await Updater(store).needs_update(requests)
    else:
        assert await Updater(store).needs_update(requests) is (state != "current")
    assert store.database == before
    build.assert_not_called()
    store.push_database.assert_not_called()


@pytest.mark.parametrize(
    ("database_update", "completed", "archive_update"),
    [
        (False, {"v1", "v2"}, False),
        (True, {"v1", "v2"}, False),
        (False, {"v1"}, True),
        (False, {"v2"}, True),  # An older missing manifest also needs catch-up.
    ],
)
async def test_check_includes_archive_only_work(
    monkeypatch, capsys, database_update, completed, archive_update
):
    settings = SimpleNamespace(github_api_url="unused", github_token=None)
    monkeypatch.setattr(cli.Settings, "from_environment", lambda: settings)
    build = AsyncMock(side_effect=AssertionError("check must not build"))
    locale_builder = SimpleNamespace(aclose=AsyncMock())
    monkeypatch.setattr(cli, "_locale_builder", lambda *_: locale_builder)
    monkeypatch.setattr(
        cli, "_prepare_artwork", AsyncMock(return_value=UpdateRequest("artwork", "v2", build))
    )

    async def prepare_locale(_builder, unit):
        return UpdateRequest(unit, "v2", build)

    monkeypatch.setattr(cli, "_prepare_locale", prepare_locale)
    updater = SimpleNamespace(needs_update=AsyncMock(return_value=database_update))
    monkeypatch.setattr(cli, "_updater", lambda _: updater)
    monkeypatch.setattr(
        cli,
        "WindowsVersionHistory",
        lambda **_: SimpleNamespace(versions=AsyncMock(return_value=("v1", "v2"))),
    )
    monkeypatch.setattr(
        cli,
        "_asset_bundle_archive",
        lambda _: SimpleNamespace(completed_versions=AsyncMock(return_value=completed)),
    )

    assert await cli._check(archive=True) == 0
    assert json.loads(capsys.readouterr().out) == {
        "update_needed": database_update or archive_update,
        "database_update": database_update,
        "archive_update": archive_update,
    }
    assert {request.unit for request in updater.needs_update.call_args.args[0]} == set(
        cli._ALL_UNITS
    )
    locale_builder.aclose.assert_awaited_once()
    build.assert_not_called()


async def test_failed_detection_is_not_reported_as_no_update(monkeypatch, capsys):
    monkeypatch.setattr(cli.Settings, "from_environment", lambda: object())
    builder = SimpleNamespace(aclose=AsyncMock())
    monkeypatch.setattr(cli, "_locale_builder", lambda *_: builder)
    monkeypatch.setattr(
        cli, "_prepare_artwork", AsyncMock(side_effect=RuntimeError("upstream down"))
    )
    monkeypatch.setattr(
        cli, "_prepare_locale", AsyncMock(side_effect=RuntimeError("upstream down"))
    )

    assert await cli._check(archive=True) == 1
    assert capsys.readouterr().out == ""
    builder.aclose.assert_awaited_once()
