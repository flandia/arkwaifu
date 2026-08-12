"""Resolve upstream-provided relative paths below an owned local directory."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


def safe_relative_path(value: str | PurePosixPath, *, context: str) -> PurePosixPath:
    """Return one portable relative path without platform-specific escape forms."""

    raw = value.as_posix() if isinstance(value, PurePosixPath) else value
    path = PurePosixPath(raw)
    windows_path = PureWindowsPath(raw)
    unsafe = (
        not raw
        or "\0" in raw
        or "\\" in raw
        or path.is_absolute()
        or windows_path.drive
        or windows_path.root
        or ".." in path.parts
        or any(":" in part for part in path.parts)
    )
    if unsafe:
        raise ValueError(f"unsafe {context}: {raw}")
    return path


def resolve_local_path(
    root: Path,
    relative: str | PurePosixPath,
    *,
    context: str,
) -> Path:
    """Resolve a portable relative path and prove that it remains below ``root``."""

    path = safe_relative_path(relative, context=context)
    resolved_root = root.resolve()
    destination = resolved_root.joinpath(*path.parts).resolve()
    try:
        destination.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(f"unsafe {context}: {relative}") from error
    return destination
