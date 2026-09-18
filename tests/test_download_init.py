"""Tests for downloader construction and lifecycle."""

from contextlib import AsyncExitStack

import pytest

from scimesh.download import (
    Downloader,
    OpenAccessDownloader,
    SciHubDownloader,
    create_downloaders,
    parse_host_concurrency,
    start_downloaders,
)


class TestParseHostConcurrency:
    def test_none(self):
        assert parse_host_concurrency(None) == (None, None)

    def test_empty(self):
        assert parse_host_concurrency("") == (None, None)

    def test_single_default(self):
        assert parse_host_concurrency("3") == (None, 3)

    def test_per_host(self):
        limits, default = parse_host_concurrency("arxiv.org=2,api.unpaywall.org=3")

        assert limits == {"arxiv.org": 2, "api.unpaywall.org": 3}
        assert default is None

    def test_default_and_per_host(self):
        assert parse_host_concurrency("3,arxiv.org=2") == ({"arxiv.org": 2}, 3)

    def test_ignores_unparseable_parts(self):
        assert parse_host_concurrency("arxiv.org=two,scihub.se=1") == ({"scihub.se": 1}, None)


class TestCreateDownloaders:
    def test_open_access_comes_first(self):
        downloaders = create_downloaders()

        assert isinstance(downloaders[0], OpenAccessDownloader)

    def test_scihub_is_opt_in(self):
        assert not any(isinstance(d, SciHubDownloader) for d in create_downloaders())
        assert any(isinstance(d, SciHubDownloader) for d in create_downloaders(use_scihub=True))

    def test_scihub_is_the_last_resort(self):
        downloaders = create_downloaders(use_scihub=True)

        assert isinstance(downloaders[-1], SciHubDownloader)

    def test_semaphores_are_shared_across_downloaders(self):
        downloaders = create_downloaders("arxiv.org=2", use_scihub=True)
        semaphores = {d._host_semaphores for d in downloaders}

        assert len(semaphores) == 1
        assert semaphores.pop() is not None

    def test_no_semaphores_without_limits(self):
        assert all(d._host_semaphores is None for d in create_downloaders())


class LifecycleDownloader(Downloader):
    """Downloader that counts open/close calls and can fail to start."""

    def __init__(self, name: str = "lifecycle", fail_start: bool = False):
        super().__init__()
        self.name = name
        self.fail_start = fail_start
        self.enters = 0
        self.exits = 0

    async def __aenter__(self):
        if self.fail_start:
            raise RuntimeError("browser not found")
        self.enters += 1
        return self

    async def __aexit__(self, *_: object) -> None:
        self.exits += 1

    async def download(self, doi: str) -> bytes | None:
        return b"%PDF-1.4"


class TestStartDownloaders:
    @pytest.mark.asyncio
    async def test_opens_and_closes_each_one(self):
        downloader = LifecycleDownloader()

        async with AsyncExitStack() as stack:
            started = await start_downloaders(stack, [downloader])
            assert started == [downloader]
            assert downloader.enters == 1

        assert downloader.exits == 1

    @pytest.mark.asyncio
    async def test_skips_downloader_that_fails_to_start(self, caplog):
        broken = LifecycleDownloader("broken", fail_start=True)
        working = LifecycleDownloader("working")

        async with AsyncExitStack() as stack:
            started = await start_downloaders(stack, [broken, working])

        assert started == [working]
        assert "browser not found" in caplog.text

    @pytest.mark.asyncio
    async def test_preserves_order(self):
        first = LifecycleDownloader("first")
        second = LifecycleDownloader("second")

        async with AsyncExitStack() as stack:
            started = await start_downloaders(stack, [first, second])

        assert [d.name for d in started] == ["first", "second"]
