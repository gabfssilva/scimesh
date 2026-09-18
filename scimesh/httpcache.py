"""httpx transport that serves provider requests from the cache."""

from __future__ import annotations

import logging
from datetime import timedelta

import httpx

from scimesh.cache import DEFAULT_RESPONSE_TTL, Cache

logger = logging.getLogger(__name__)


class CachingTransport(httpx.AsyncBaseTransport):
    """Serves GET responses from the cache and stores the successful ones.

    Only 200 responses to GET requests are cached, keyed by URL, so pagination
    caches page by page. Errors always go to the network, so a provider that
    failed is retried rather than remembered.

    Args:
        cache: Where responses are stored.
        ttl: How long a stored response stays usable.
        refresh: Skip reads but keep writes, to deliberately go past a stale entry.
        transport: The transport doing the real requests.
    """

    def __init__(
        self,
        cache: Cache,
        ttl: timedelta = DEFAULT_RESPONSE_TTL,
        refresh: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._cache = cache
        self._ttl = ttl
        self._refresh = refresh
        self._transport = transport or httpx.AsyncHTTPTransport()

    @property
    def cache(self) -> Cache:
        """Where this transport reads and writes responses."""
        return self._cache

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            return await self._transport.handle_async_request(request)

        url = str(request.url)

        if not self._refresh:
            cached = self._cache.response(url, self._ttl)
            if cached is not None:
                body, content_type = cached
                logger.debug("Cached response for %s", url)
                return _response(200, body, content_type)

        response = await self._transport.handle_async_request(request)
        if response.status_code != 200:
            return response

        body = await response.aread()
        await response.aclose()
        content_type = response.headers.get("content-type")
        self._cache.save_response(url, body, content_type)

        return _response(200, body, content_type)

    async def aclose(self) -> None:
        await self._transport.aclose()


def _response(status: int, body: bytes, content_type: str | None) -> httpx.Response:
    # The body is already decoded here, so the original content-encoding and
    # content-length headers would make httpx decode it a second time.
    headers = {"content-type": content_type} if content_type else {}
    return httpx.Response(status, content=body, headers=headers)


__all__ = ["CachingTransport"]
