"""Tests for PlaywrightDownloader."""

import pytest

from scimesh.download.playwright import PlaywrightConfig, PlaywrightDownloader


@pytest.mark.asyncio
async def test_failed_browser_launch_releases_resources(monkeypatch):
    monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
    downloader = PlaywrightDownloader(config=PlaywrightConfig(browser="missing-browser"))

    with pytest.raises(ValueError, match="Unknown browser"):
        await downloader.__aenter__()

    assert downloader._playwright is None
    assert downloader._browser is None
    assert downloader._client is None
