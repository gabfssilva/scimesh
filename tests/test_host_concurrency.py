# tests/test_host_concurrency.py
"""Tests for per-host concurrency control."""

import asyncio

import pytest

from scimesh.download.host_concurrency import HostSemaphores


class TestHostSemaphores:
    """Tests for HostSemaphores."""

    def test_no_limits_by_default(self):
        """No limits are applied when initialized without limits."""
        semaphores = HostSemaphores()
        assert semaphores.get_limit("example.com") is None

    def test_limits_can_be_configured(self):
        """Limits can be configured at initialization."""
        semaphores = HostSemaphores(
            {
                "arxiv.org": 2,
                "api.unpaywall.org": 3,
            }
        )
        assert semaphores.get_limit("arxiv.org") == 2
        assert semaphores.get_limit("api.unpaywall.org") == 3
        assert semaphores.get_limit("other.com") is None

    def test_set_limit(self):
        """Limits can be set or updated after initialization."""
        semaphores = HostSemaphores()
        semaphores.set_limit("example.com", 5)
        assert semaphores.get_limit("example.com") == 5

    @pytest.mark.asyncio
    async def test_acquire_with_url(self):
        """Semaphore can be acquired using a full URL."""
        semaphores = HostSemaphores({"example.com": 2})

        async with semaphores.acquire("https://example.com/path/to/resource"):
            # Semaphore should be acquired
            assert "example.com" in semaphores._semaphores

    @pytest.mark.asyncio
    async def test_acquire_with_host(self):
        """Semaphore can be acquired using a hostname directly."""
        semaphores = HostSemaphores({"example.com": 2})

        async with semaphores.acquire_host("example.com"):
            # Semaphore should be acquired
            assert "example.com" in semaphores._semaphores

    @pytest.mark.asyncio
    async def test_no_limit_no_blocking(self):
        """Hosts without limits don't block."""
        semaphores = HostSemaphores({"limited.com": 1})

        # This should not block since "unlimited.com" has no limit
        async with semaphores.acquire("https://unlimited.com/resource"):
            pass

    @pytest.mark.asyncio
    async def test_different_hosts_independent(self):
        """Semaphores for different hosts are independent."""
        semaphores = HostSemaphores(
            {
                "host1.com": 1,
                "host2.com": 1,
            }
        )

        results = []

        async def access_host1():
            async with semaphores.acquire_host("host1.com"):
                results.append("host1_start")
                await asyncio.sleep(0.1)
                results.append("host1_end")

        async def access_host2():
            async with semaphores.acquire_host("host2.com"):
                results.append("host2_start")
                await asyncio.sleep(0.05)
                results.append("host2_end")

        # Both should run concurrently since they're different hosts
        await asyncio.gather(access_host1(), access_host2())

        # host2 should finish first since it's faster
        assert results == ["host1_start", "host2_start", "host2_end", "host1_end"]

    @pytest.mark.asyncio
    async def test_same_host_limited(self):
        """Multiple requests to same host respect limit."""
        semaphores = HostSemaphores({"example.com": 1})

        results = []

        async def request1():
            async with semaphores.acquire_host("example.com"):
                results.append("req1_start")
                await asyncio.sleep(0.1)
                results.append("req1_end")

        async def request2():
            async with semaphores.acquire_host("example.com"):
                results.append("req2_start")
                await asyncio.sleep(0.05)
                results.append("req2_end")

        await asyncio.gather(request1(), request2())

        # Request 2 should wait for request 1 to finish
        assert results == ["req1_start", "req1_end", "req2_start", "req2_end"]

    @pytest.mark.asyncio
    async def test_concurrent_requests_within_limit(self):
        """Multiple concurrent requests allowed within limit."""
        semaphores = HostSemaphores({"example.com": 2})

        active_count = 0
        max_active = 0

        async def request():
            nonlocal active_count, max_active
            async with semaphores.acquire_host("example.com"):
                active_count += 1
                max_active = max(max_active, active_count)
                await asyncio.sleep(0.05)
                active_count -= 1

        # Run 4 concurrent requests with limit of 2
        await asyncio.gather(*[request() for _ in range(4)])

        # At most 2 should have been active at once
        assert max_active == 2

    @pytest.mark.asyncio
    async def test_semaphore_reused_for_same_host(self):
        """Same semaphore is reused for the same host."""
        semaphores = HostSemaphores({"example.com": 2})

        async with semaphores.acquire_host("example.com"):
            sem1 = semaphores._semaphores.get("example.com")

        async with semaphores.acquire_host("example.com"):
            sem2 = semaphores._semaphores.get("example.com")

        assert sem1 is sem2

    def test_set_limit_clears_existing_semaphore(self):
        """Updating a limit clears the existing semaphore."""
        semaphores = HostSemaphores({"example.com": 2})
        # Access to create the semaphore (simulate)
        semaphores._get_semaphore("example.com")
        assert "example.com" in semaphores._semaphores

        # Update limit should clear the semaphore
        semaphores.set_limit("example.com", 5)
        assert "example.com" not in semaphores._semaphores

    def test_default_limit(self):
        """Default limit applies to unlisted hosts."""
        semaphores = HostSemaphores(default=3)
        assert semaphores.get_limit("any-host.com") == 3

    def test_explicit_overrides_default(self):
        """Explicit limit overrides default."""
        semaphores = HostSemaphores({"example.com": 2}, default=5)
        assert semaphores.get_limit("example.com") == 2
        assert semaphores.get_limit("other.com") == 5

    @pytest.mark.asyncio
    async def test_default_creates_semaphore(self):
        """Default limit creates semaphore for any host."""
        semaphores = HostSemaphores(default=2)

        async with semaphores.acquire_host("new-host.com"):
            assert "new-host.com" in semaphores._semaphores
