import json
import logging
import os

import pytest

from arkwaifu_updateloop.cli import (
    _configure_logging,
    _JsonFormatter,
    _parser,
    _validate_arguments,
    main,
)


def test_json_formatter_keeps_exception_details():
    try:
        raise RuntimeError("diagnostic")
    except RuntimeError:
        record = logging.LogRecord(
            "test", logging.ERROR, __file__, 1, "failed", (), exc_info=__import__("sys").exc_info()
        )

    payload = json.loads(_JsonFormatter().format(record))

    assert payload["message"] == "failed"
    assert "RuntimeError: diagnostic" in payload["exception"]


def test_json_formatter_keeps_structured_artwork_action_fields():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "artwork action", (), None)
    for key, value in {
        "action": "version",
        "status": "cached",
        "res_version": "artwork-v1",
        "resource": "avg/images/example.ab",
        "current": 3,
        "total": 7,
        "elapsed_ms": 12.5,
    }.items():
        setattr(record, key, value)

    payload = json.loads(_JsonFormatter().format(record))

    assert payload == {
        "timestamp": payload["timestamp"],
        "level": "info",
        "message": "artwork action",
        "action": "version",
        "status": "cached",
        "res_version": "artwork-v1",
        "resource": "avg/images/example.ab",
        "current": 3,
        "total": 7,
        "elapsed_ms": 12.5,
    }


def test_incomplete_upstream_suppression_flag_disables_only_its_logger():
    args = _parser().parse_args(["run", "EN", "--suppress-incomplete-upstream-warnings"])

    try:
        _configure_logging(
            suppress_incomplete_upstream_warnings=args.suppress_incomplete_upstream_warnings
        )
        assert args.units == ["EN"]
        assert args.suppress_incomplete_upstream_warnings is True

        assert logging.getLogger("arkwaifu_updateloop.incomplete_upstream").disabled is True
        assert logging.getLogger("arkwaifu_updateloop").disabled is False
    finally:
        logging.getLogger("arkwaifu_updateloop.incomplete_upstream").disabled = False


def test_no_cache_flag_is_available_on_run():
    args = _parser().parse_args(["run", "artwork", "--no-cache"])

    assert args.units == ["artwork"]
    assert args.no_cache is True


def test_archive_is_available_for_default_or_explicit_artwork_runs():
    parser = _parser()
    for arguments in (["run", "--archive"], ["run", "artwork", "--archive"]):
        args = parser.parse_args(arguments)
        _validate_arguments(parser, args)
        assert args.archive is True


def test_archive_can_be_combined_with_complete():
    parser = _parser()
    args = parser.parse_args(["run", "artwork", "--complete", "--archive"])

    _validate_arguments(parser, args)

    assert args.complete is True
    assert args.archive is True


@pytest.mark.parametrize("units", [["CN"], ["EN", "JP"]])
def test_archive_rejects_locale_only_runs(units):
    parser = _parser()
    args = parser.parse_args(["run", *units, "--archive"])

    with pytest.raises(SystemExit, match="2"):
        _validate_arguments(parser, args)


def test_main_loads_dotenv_without_overriding_process_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "ARKWAIFU_S3_BUCKET=file-bucket\n"
        "ARKWAIFU_S3_ACCESS_KEY_ID=file-access\n"
        "ARKWAIFU_DOWNLOAD_WORKERS=3\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ARKWAIFU_S3_BUCKET", "process-bucket")
    for name in ("ARKWAIFU_S3_ACCESS_KEY_ID", "ARKWAIFU_DOWNLOAD_WORKERS"):
        monkeypatch.delenv(name, raising=False)
    observed = []

    async def capture(*_args, **_kwargs):
        observed.append(
            (
                os.environ["ARKWAIFU_S3_BUCKET"],
                os.environ["ARKWAIFU_S3_ACCESS_KEY_ID"],
                os.environ["ARKWAIFU_DOWNLOAD_WORKERS"],
            )
        )
        return 0

    monkeypatch.setattr("arkwaifu_updateloop.cli._run", capture)

    with pytest.raises(SystemExit, match="0"):
        main(["run", "CN"])

    assert observed == [("process-bucket", "file-access", "3")]


def test_complete_is_available_for_exactly_the_artwork_unit():
    parser = _parser()
    args = parser.parse_args(["run", "artwork", "--complete"])

    _validate_arguments(parser, args)

    assert args.complete is True


@pytest.mark.parametrize(
    "arguments",
    [
        ["run", "--complete"],
        ["run", "CN", "--complete"],
        ["run", "artwork", "CN", "--complete"],
        ["run", "artwork", "artwork", "--complete"],
        ["run", "artwork", "--complete", "--force"],
    ],
)
def test_complete_rejects_default_multiple_non_artwork_and_force(arguments):
    parser = _parser()
    args = parser.parse_args(arguments)

    with pytest.raises(SystemExit, match="2"):
        _validate_arguments(parser, args)


@pytest.mark.parametrize("units", [[], ["artwork"], ["artwork", "EN"]])
def test_force_rejects_default_or_explicit_artwork_units(units):
    parser = _parser()
    args = parser.parse_args(["run", *units, "--force"])

    with pytest.raises(SystemExit, match="2"):
        _validate_arguments(parser, args)
