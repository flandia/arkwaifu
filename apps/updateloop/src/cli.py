"""Provide the command-line interface of the Arkwaifu update loop."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import selectors
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from .config import Settings
from .domain import ArtManifest, LocaleManifest, LocaleUnit
from .object_store import S3ObjectStore
from .updater import Update, Updateloop, UpdateUnit
from .upstream import LiveArtBuilder, LiveLocaleBuilder, UpstreamCache
from .upstream.art_history import LiveWindowsVersionHistory

_ALL_UNITS: tuple[UpdateUnit, ...] = ("art", "CN", "EN", "JP", "KR", "TW")
_STRUCTURED_LOG_FIELDS = (
    "action",
    "status",
    "res_version",
    "resource",
    "current",
    "total",
    "elapsed_ms",
)
_LOGGER = logging.getLogger(__name__)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        payload.update(
            (field, getattr(record, field))
            for field in _STRUCTURED_LOG_FIELDS
            if hasattr(record, field)
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def _configure_logging(*, suppress_incomplete_upstream_warnings: bool = False) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger(
        "arkwaifu_updateloop.incomplete_upstream"
    ).disabled = suppress_incomplete_upstream_warnings


def _unit(value: str) -> UpdateUnit:
    normalized = "art" if value.lower() == "art" else value.upper()
    if normalized not in _ALL_UNITS:
        raise argparse.ArgumentTypeError(f"unknown update unit: {value}")
    return cast(UpdateUnit, normalized)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="updateloop")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="update selected units")
    run.add_argument("units", nargs="*", type=_unit)
    run.add_argument("--force", action="store_true")
    run.add_argument(
        "--complete",
        action="store_true",
        help="rebuild art additively across every recorded Windows resVersion",
    )
    run.add_argument(
        "--no-cache",
        action="store_true",
        help="use temporary storage without reading or writing ./.cache",
    )
    run.add_argument(
        "--suppress-incomplete-upstream-warnings",
        action="store_true",
        help="do not warn about expected incomplete upstream data",
    )
    return parser


def _validate_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Enforce run-mode combinations which argparse cannot express declaratively."""

    if args.command == "run" and args.complete:
        if args.force:
            parser.error("--complete cannot be combined with --force")
        if args.units != ["art"]:
            parser.error("--complete requires exactly one update unit: art")
    if args.command == "run" and args.force and (not args.units or "art" in args.units):
        parser.error("--force is available only for locale-only updates")


def _updateloop(settings: Settings) -> Updateloop:
    return Updateloop(
        S3ObjectStore(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            endpoint_url=settings.s3_endpoint_url,
            path_style=settings.s3_path_style,
        ),
    )


async def _prepare_art(
    settings: Settings,
    cache: UpstreamCache,
    *,
    complete: bool = False,
) -> Update:
    builder = LiveArtBuilder(
        version_url=settings.art_version_url,
        asset_base_url=settings.art_asset_base_url,
        download_workers=settings.download_workers,
        extraction_workers=settings.extraction_workers,
        cache=cache,
    )
    res_version = await builder.detect_version()

    if complete:
        history = LiveWindowsVersionHistory(
            github_api_url=settings.github_api_url,
            github_raw_url="https://raw.githubusercontent.com",
            github_token=settings.github_token,
            cache=cache,
        )
        versions = await history.versions(res_version)

        async def build_complete(_active: str | None, _force: bool) -> ArtManifest:
            return await builder.build_history(versions)

        return Update("art", res_version, build_complete, complete=True)

    async def build(active: str | None, force: bool) -> ArtManifest:
        return await builder.build(res_version, active, force)

    return Update("art", res_version, build)


def _locale_builder(
    settings: Settings,
    cache: UpstreamCache,
) -> LiveLocaleBuilder:
    return LiveLocaleBuilder(
        github_api_url=settings.github_api_url,
        github_token=settings.github_token,
        cache=cache,
    )


async def _prepare_locale(
    builder: LiveLocaleBuilder,
    unit: LocaleUnit,
) -> Update:
    res_version = await builder.detect_version(unit)

    async def build(active: str | None, force: bool) -> LocaleManifest:
        return await builder.build(unit, res_version, active, force)

    return Update(unit, res_version, build)


async def _run(
    units: list[UpdateUnit],
    *,
    force: bool,
    complete: bool = False,
    use_cache: bool = True,
) -> int:
    settings = Settings.from_environment()
    if use_cache:
        cache = UpstreamCache(Path.cwd() / ".cache")
        _LOGGER.info("cache=enabled path=%s", cache.root)
        return await _run_with_cache(
            settings,
            units,
            force=force,
            complete=complete,
            cache=cache,
        )
    with tempfile.TemporaryDirectory(prefix="arkwaifu-run-") as temporary:
        cache = UpstreamCache(Path(temporary) / "upstream")
        _LOGGER.info("cache=ephemeral path=%s", cache.root)
        return await _run_with_cache(
            settings,
            units,
            force=force,
            complete=complete,
            cache=cache,
        )


async def _run_with_cache(
    settings: Settings,
    units: list[UpdateUnit],
    *,
    force: bool,
    complete: bool,
    cache: UpstreamCache,
) -> int:
    """Prepare requested datasets concurrently and publish them as one database."""

    requested_units = tuple(dict.fromkeys(units or _ALL_UNITS))
    updater = _updateloop(settings)
    locale_builder = (
        _locale_builder(settings, cache) if any(unit != "art" for unit in requested_units) else None
    )
    preparation_tasks: dict[UpdateUnit, asyncio.Task[Update]] = {}
    try:
        for unit in requested_units:
            if unit == "art":
                preparation = (
                    _prepare_art(settings, cache, complete=True)
                    if complete
                    else _prepare_art(settings, cache)
                )
            else:
                if locale_builder is None:
                    raise AssertionError("locale builder was not created")
                preparation = _prepare_locale(locale_builder, cast(LocaleUnit, unit))
            preparation_tasks[unit] = asyncio.create_task(preparation, name=f"prepare-{unit}")

        updates: list[Update] = []
        preparation_failed = False
        outcomes = await asyncio.gather(*preparation_tasks.values(), return_exceptions=True)
        for unit, outcome in zip(preparation_tasks, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                preparation_failed = True
                _LOGGER.error(
                    "unit=%s status=failed",
                    unit,
                    exc_info=(type(outcome), outcome, outcome.__traceback__),
                )
            else:
                updates.append(outcome)
        if preparation_failed:
            return 1
        try:
            results = await updater.run(updates, force=force)
        except Exception:
            _LOGGER.exception("database status=failed units=%s", requested_units)
            return 1
        for result in results:
            _LOGGER.info(
                "unit=%s status=%s res_version=%s",
                result.unit,
                result.status,
                result.res_version,
            )
        return 0
    finally:
        unfinished = [task for task in preparation_tasks.values() if not task.done()]
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.gather(*unfinished, return_exceptions=True)
        if locale_builder is not None:
            await locale_builder.aclose()


def main(argv: list[str] | None = None) -> None:
    """Run the command-line interface and exit with the update result."""

    parser = _parser()
    args = parser.parse_args(argv)
    _validate_arguments(parser, args)
    _configure_logging(
        suppress_incomplete_upstream_warnings=args.suppress_incomplete_upstream_warnings
    )
    if args.command == "run":
        if sys.platform == "win32":
            loop_factory = lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
            with asyncio.Runner(loop_factory=loop_factory) as runner:
                exit_code = runner.run(
                    _run(
                        args.units,
                        force=args.force,
                        complete=args.complete,
                        use_cache=not args.no_cache,
                    )
                )
        else:
            exit_code = asyncio.run(
                _run(
                    args.units,
                    force=args.force,
                    complete=args.complete,
                    use_cache=not args.no_cache,
                )
            )
        raise SystemExit(exit_code)
    raise AssertionError(f"unhandled command: {args.command}")
