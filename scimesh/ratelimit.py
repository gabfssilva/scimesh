"""httpx transport that waits out short rate limits and reports long ones."""

from __future__ import annotations

import asyncio
import logging

import httpx

from scimesh.exceptions import ProviderError

logger = logging.getLogger(__name__)

DEFAULT_MAX_WAIT = 30.0
DEFAULT_ATTEMPTS = 3


class RateLimitedTransport(httpx.AsyncBaseTransport):
    """Retries 429 responses, honouring ``Retry-After``.

    A short wait is slept through and retried. A long one is not worth holding
    a command open for, so it is raised as a ``ProviderError`` saying when the
    quota comes back, instead of the raw status error.

    Args:
        max_wait: Longest ``Retry-After`` worth waiting for, in seconds.
        attempts: How many times to send the request before giving up.
        transport: The transport doing the real requests.
    """

    def __init__(
        self,
        max_wait: float = DEFAULT_MAX_WAIT,
        attempts: int = DEFAULT_ATTEMPTS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._max_wait = max_wait
        self._attempts = attempts
        self._transport = transport or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for attempt in range(1, self._attempts + 1):
            response = await self._transport.handle_async_request(request)
            if response.status_code != 429:
                return response

            await response.aclose()
            wait = _retry_after(response, attempt)
            host = request.url.host

            if wait > self._max_wait:
                raise ProviderError(host, f"rate limited, quota returns in {_human(wait)}")

            logger.warning("Rate limited by %s, retrying in %.1fs", host, wait)
            await asyncio.sleep(wait)

        raise ProviderError(request.url.host, f"rate limited after {self._attempts} attempts")

    async def aclose(self) -> None:
        await self._transport.aclose()


def _retry_after(response: httpx.Response, attempt: int) -> float:
    """Seconds to wait: what the server asked for, else exponential backoff."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    return float(2 ** (attempt - 1))


def _human(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}min"
    return f"{seconds / 3600:.1f}h"


__all__ = ["RateLimitedTransport"]
