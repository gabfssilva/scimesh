"""Tests for the caching HTTP transport."""

from datetime import timedelta

import httpx
import pytest

from scimesh.cache import Cache
from scimesh.httpcache import CachingTransport

URL = "https://api.example.com/works?page=1"


@pytest.fixture
def cache(tmp_path):
    with Cache(tmp_path / "scimesh") as cache:
        yield cache


class Upstream(httpx.AsyncBaseTransport):
    """Counts requests and answers with a canned response."""

    def __init__(self, status: int = 200, body: bytes = b'{"ok": true}', headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {"content-type": "application/json"}
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, content=self.body, headers=self.headers)


async def fetch(transport: CachingTransport, url: str = URL, method: str = "GET") -> httpx.Response:
    async with httpx.AsyncClient(transport=transport) as client:
        return await client.request(method, url)


class TestCaching:
    async def test_second_request_is_served_from_the_cache(self, cache):
        upstream = Upstream()
        transport = CachingTransport(cache, transport=upstream)

        first = await fetch(transport)
        second = await fetch(transport)

        assert first.json() == second.json() == {"ok": True}
        assert len(upstream.requests) == 1

    async def test_content_type_survives(self, cache):
        transport = CachingTransport(cache, transport=Upstream())

        await fetch(transport)
        response = await fetch(transport)

        assert response.headers["content-type"] == "application/json"

    async def test_distinct_urls_are_fetched_separately(self, cache):
        upstream = Upstream()
        transport = CachingTransport(cache, transport=upstream)

        await fetch(transport, "https://api.example.com/works?page=1")
        await fetch(transport, "https://api.example.com/works?page=2")

        assert len(upstream.requests) == 2

    async def test_expired_entries_are_refetched(self, cache):
        upstream = Upstream()
        transport = CachingTransport(cache, ttl=timedelta(0), transport=upstream)

        await fetch(transport)
        await fetch(transport)

        assert len(upstream.requests) == 2

    async def test_refresh_ignores_the_cache_but_still_writes(self, cache):
        upstream = Upstream()

        await fetch(CachingTransport(cache, transport=upstream))
        await fetch(CachingTransport(cache, refresh=True, transport=upstream))

        assert len(upstream.requests) == 2

        await fetch(CachingTransport(cache, transport=upstream))

        assert len(upstream.requests) == 2

    async def test_errors_are_not_cached(self, cache):
        upstream = Upstream(status=429, body=b"slow down")
        transport = CachingTransport(cache, transport=upstream)

        first = await fetch(transport)
        await fetch(transport)

        assert first.status_code == 429
        assert len(upstream.requests) == 2
        assert cache.stats().responses == 0

    async def test_non_get_requests_pass_through(self, cache):
        upstream = Upstream()
        transport = CachingTransport(cache, transport=upstream)

        await fetch(transport, method="POST")
        await fetch(transport, method="POST")

        assert len(upstream.requests) == 2
        assert cache.stats().responses == 0

    async def test_compressed_bodies_are_stored_decoded(self, cache):
        import gzip

        upstream = Upstream(
            body=gzip.compress(b'{"ok": true}'),
            headers={"content-type": "application/json", "content-encoding": "gzip"},
        )
        transport = CachingTransport(cache, transport=upstream)

        assert (await fetch(transport)).json() == {"ok": True}
        assert (await fetch(transport)).json() == {"ok": True}
