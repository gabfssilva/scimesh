"""Tests for the rate-limit aware transport."""

import httpx
import pytest

from scimesh.exceptions import ProviderError
from scimesh.ratelimit import RateLimitedTransport

URL = "https://api.example.com/works"


class Upstream(httpx.AsyncBaseTransport):
    """Answers with a queue of responses, one per request."""

    def __init__(self, *responses: httpx.Response):
        self.queue = list(responses)
        self.requests = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        return self.queue.pop(0) if self.queue else httpx.Response(200, json={"ok": True})


@pytest.fixture
def slept(monkeypatch):
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr("scimesh.ratelimit.asyncio.sleep", sleep)
    return waits


def too_many(retry_after: str | None = None) -> httpx.Response:
    headers = {"retry-after": retry_after} if retry_after else {}
    return httpx.Response(429, headers=headers, text="slow down")


async def fetch(transport: RateLimitedTransport) -> httpx.Response:
    async with httpx.AsyncClient(transport=transport) as client:
        return await client.get(URL)


class TestRateLimitedTransport:
    async def test_passes_successful_responses_through(self, slept):
        upstream = Upstream(httpx.Response(200, json={"ok": True}))

        response = await fetch(RateLimitedTransport(transport=upstream))

        assert response.json() == {"ok": True}
        assert slept == []

    async def test_other_errors_are_not_retried(self, slept):
        upstream = Upstream(httpx.Response(404, text="nope"))

        response = await fetch(RateLimitedTransport(transport=upstream))

        assert response.status_code == 404
        assert upstream.requests == 1

    async def test_waits_out_a_short_retry_after(self, slept):
        upstream = Upstream(too_many("5"), httpx.Response(200, json={"ok": True}))

        response = await fetch(RateLimitedTransport(transport=upstream))

        assert response.json() == {"ok": True}
        assert slept == [5.0]
        assert upstream.requests == 2

    async def test_backs_off_when_the_server_says_nothing(self, slept):
        upstream = Upstream(too_many(), too_many(), httpx.Response(200, json={"ok": True}))

        await fetch(RateLimitedTransport(transport=upstream))

        assert slept == [1.0, 2.0]

    async def test_long_waits_are_reported_not_slept(self, slept):
        upstream = Upstream(too_many("5432"))

        with pytest.raises(ProviderError, match="quota returns in 1.5h"):
            await fetch(RateLimitedTransport(transport=upstream))

        assert slept == []
        assert upstream.requests == 1

    async def test_gives_up_after_the_last_attempt(self, slept):
        upstream = Upstream(too_many("1"), too_many("1"), too_many("1"))

        with pytest.raises(ProviderError, match="after 3 attempts"):
            await fetch(RateLimitedTransport(attempts=3, transport=upstream))

        assert upstream.requests == 3

    async def test_names_the_host(self, slept):
        upstream = Upstream(too_many("9999"))

        with pytest.raises(ProviderError, match="api.example.com"):
            await fetch(RateLimitedTransport(transport=upstream))
