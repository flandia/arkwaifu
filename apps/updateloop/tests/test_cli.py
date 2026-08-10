import json
import logging

from arkwaifu_updateloop.cli import _configure_logging, _JsonFormatter, _parser


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
