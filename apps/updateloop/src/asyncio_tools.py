"""Small asyncio primitives shared by updater resource owners."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable


async def await_owned[Value](awaitable: Awaitable[Value]) -> Value:
    """Let owned work settle before propagating cancellation of its caller.

    Shielding alone keeps the owned task alive but lets its caller unwind. This
    helper also drains the task, including through repeated cancellation, so a
    surrounding temporary directory or lock cannot disappear underneath it.
    """

    owned = asyncio.ensure_future(awaitable)
    caller = asyncio.current_task()
    cancellation: asyncio.CancelledError | None = None

    while True:
        try:
            value = await asyncio.shield(owned)
        except asyncio.CancelledError as error:
            if caller is None or not caller.cancelling():
                raise
            if cancellation is None:
                cancellation = error
            if not owned.done():
                continue
            try:
                owned.result()
            except BaseException as owned_error:
                if owned_error is cancellation:
                    raise cancellation
                raise cancellation from owned_error
            raise cancellation
        except BaseException as error:
            if cancellation is not None:
                raise cancellation from error
            raise
        if cancellation is not None:
            raise cancellation
        return value
