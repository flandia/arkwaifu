"""Retry small upstream version reads without repeating preparation or publication."""

import asyncio
import time
from email.utils import parsedate_to_datetime

import httpx


async def version_response(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """Attempt a version GET at most three times, with at most 60 seconds of backoff."""
    waited = 0
    for attempt in range(3):
        delay = 5 * (attempt + 1)
        try:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as error:
            response = error.response
            rate_limited = response.status_code == 429 or (
                response.status_code == 403
                and (
                    response.headers.get("x-ratelimit-remaining") == "0"
                    or "rate limit" in response.text.lower()
                )
            )
            if not rate_limited and response.status_code not in (500, 502, 503, 504):
                raise
            if retry_after := response.headers.get("retry-after"):
                try:
                    delay = max(0, float(retry_after))
                except ValueError:
                    delay = max(0, parsedate_to_datetime(retry_after).timestamp() - time.time())
            elif rate_limited and (reset := response.headers.get("x-ratelimit-reset")):
                delay = max(0, float(reset) - time.time())
            elif rate_limited:
                delay = 60
            if attempt == 2 or waited + delay > 60:
                raise
        except httpx.TransportError:
            if attempt == 2:
                raise
        waited += delay
        await asyncio.sleep(delay)
    raise AssertionError("Version retry loop exhausted without a result")
