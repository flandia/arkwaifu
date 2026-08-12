import json
import logging

import pytest

from arkwaifu_updateloop.cli import (
    _configure_logging,
    _JsonFormatter,
    _parser,
    _validate_arguments,
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


def test_json_formatter_keeps_structured_art_action_fields():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "art action", (), None)
    for key, value in {
        "action": "version",
        "status": "cached",
        "res_version": "art-v1",
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
        "message": "art action",
        "action": "version",
        "status": "cached",
        "res_version": "art-v1",
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
    args = _parser().parse_args(["run", "art", "--no-cache"])

    assert args.units == ["art"]
    assert args.no_cache is True


def test_complete_is_available_for_exactly_the_art_unit():
    parser = _parser()
    args = parser.parse_args(["run", "art", "--complete"])

    _validate_arguments(parser, args)

    assert args.complete is True


@pytest.mark.parametrize(
    "arguments",
    [
        ["run", "--complete"],
        ["run", "CN", "--complete"],
        ["run", "art", "CN", "--complete"],
        ["run", "art", "art", "--complete"],
        ["run", "art", "--complete", "--force"],
    ],
)
def test_complete_rejects_default_multiple_non_art_and_force(arguments):
    parser = _parser()
    args = parser.parse_args(arguments)

    with pytest.raises(SystemExit, match="2"):
        _validate_arguments(parser, args)


@pytest.mark.parametrize("units", [[], ["art"], ["art", "EN"]])
def test_force_rejects_default_or_explicit_art_units(units):
    parser = _parser()
    args = parser.parse_args(["run", *units, "--force"])

    with pytest.raises(SystemExit, match="2"):
        _validate_arguments(parser, args)
