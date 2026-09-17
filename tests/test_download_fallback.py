# tests/test_download_fallback.py
"""Tests for FallbackDownloader."""

import pytest

from scimesh.download import FallbackDownloader
from scimesh.download.base import Downloader


class MockDownloader(Downloader):
    """Mock downloader for testing."""

    def __init__(self, name: str, result: bytes | None = None, should_raise: bool = False):
        super().__init__()
        self.name = name
        self._result = result
        self._should_raise = should_raise
        self.download_called = False

    async def download(self, doi: str) -> bytes | None:
        self.download_called = True
        if self._should_raise:
            raise Exception(f"{self.name} failed")
        return self._result


class CountingDownloader(MockDownloader):
    """Mock downloader that counts open/close calls."""

    def __init__(self, name: str):
        super().__init__(name)
        self.enters = 0
        self.exits = 0

    async def __aenter__(self):
        self.enters += 1
        return self

    async def __aexit__(self, *args):
        self.exits += 1


class TestFallbackDownloader:
    """Tests for FallbackDownloader."""

    @pytest.mark.asyncio
    async def test_returns_first_successful_result(self):
        """First downloader that returns a result wins."""
        d1 = MockDownloader("first", result=b"pdf from first")
        d2 = MockDownloader("second", result=b"pdf from second")

        fallback = FallbackDownloader(d1, d2)
        async with fallback:
            result = await fallback.download("10.1234/test")

        assert result == b"pdf from first"
        assert d1.download_called
        assert not d2.download_called  # Should not be called

    @pytest.mark.asyncio
    async def test_tries_next_on_none(self):
        """Tries next downloader when first returns None."""
        d1 = MockDownloader("first", result=None)
        d2 = MockDownloader("second", result=b"pdf from second")

        fallback = FallbackDownloader(d1, d2)
        async with fallback:
            result = await fallback.download("10.1234/test")

        assert result == b"pdf from second"
        assert d1.download_called
        assert d2.download_called

    @pytest.mark.asyncio
    async def test_tries_next_on_exception(self):
        """Tries next downloader when first raises exception."""
        d1 = MockDownloader("first", should_raise=True)
        d2 = MockDownloader("second", result=b"pdf from second")

        fallback = FallbackDownloader(d1, d2)
        async with fallback:
            result = await fallback.download("10.1234/test")

        assert result == b"pdf from second"
        assert d1.download_called
        assert d2.download_called

    @pytest.mark.asyncio
    async def test_returns_none_when_all_fail(self):
        """Returns None when all downloaders fail."""
        d1 = MockDownloader("first", result=None)
        d2 = MockDownloader("second", result=None)

        fallback = FallbackDownloader(d1, d2)
        async with fallback:
            result = await fallback.download("10.1234/test")

        assert result is None
        assert d1.download_called
        assert d2.download_called

    @pytest.mark.asyncio
    async def test_context_manager_opens_all(self):
        """Context manager opens all underlying downloaders."""
        d1 = CountingDownloader("first")
        d2 = CountingDownloader("second")

        fallback = FallbackDownloader(d1, d2)
        async with fallback:
            assert (d1.enters, d2.enters) == (1, 1)
            assert (d1.exits, d2.exits) == (0, 0)

        assert (d1.exits, d2.exits) == (1, 1)

    @pytest.mark.asyncio
    async def test_single_downloader(self):
        """Works with a single downloader."""
        d1 = MockDownloader("only", result=b"pdf")

        fallback = FallbackDownloader(d1)
        async with fallback:
            result = await fallback.download("10.1234/test")

        assert result == b"pdf"

    @pytest.mark.asyncio
    async def test_name_attribute(self):
        """Has correct name attribute."""
        fallback = FallbackDownloader()
        assert fallback.name == "fallback"


class FailingStartDownloader(MockDownloader):
    """Downloader whose startup fails, e.g. a missing browser."""

    async def __aenter__(self):
        raise RuntimeError(f"{self.name} could not start")


class TestFallbackDownloaderStartup:
    @pytest.mark.asyncio
    async def test_skips_downloader_that_fails_to_start(self, caplog):
        broken = FailingStartDownloader("broken", result=b"never")
        working = MockDownloader("working", result=b"pdf")

        fallback = FallbackDownloader(broken, working)
        async with fallback:
            result = await fallback.download("10.1234/test")

        assert result == b"pdf"
        assert not broken.download_called
        assert "broken could not start" in caplog.text
