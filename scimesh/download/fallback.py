# scimesh/download/fallback.py
"""Fallback-aware downloader that tries multiple downloaders in order."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from scimesh.download.base import Downloader

if TYPE_CHECKING:
    from scimesh.download.host_concurrency import HostSemaphores

logger = logging.getLogger(__name__)


class FallbackDownloader(Downloader):
    """Downloader that tries multiple downloaders in order until one succeeds.

    Example:
        >>> # Share per-host semaphores across all downloaders
        >>> semaphores = HostSemaphores({
        ...     "arxiv.org": 2,
        ...     "api.unpaywall.org": 3,
        ...     "sci-hub.se": 2,
        ... })
        >>> downloader = FallbackDownloader(
        ...     OpenAccessDownloader(host_semaphores=semaphores),
        ...     SciHubDownloader(host_semaphores=semaphores),
        ... )
        >>> async with downloader:
        ...     pdf = await downloader.download("10.1234/paper")
    """

    name = "fallback"

    def __init__(
        self,
        *downloaders: Downloader,
        host_semaphores: HostSemaphores | None = None,
    ):
        """Initialize with multiple downloaders.

        Args:
            *downloaders: Downloaders to try in order. Each should have the
                same host_semaphores for consistent concurrency control.
            host_semaphores: Optional shared per-host semaphores. Note: it's
                recommended to pass this to individual downloaders instead.
        """
        super().__init__(host_semaphores=host_semaphores)
        self._downloaders = downloaders

    async def __aenter__(self) -> FallbackDownloader:
        """Open all underlying downloaders."""
        await super().__aenter__()
        for d in self._downloaders:
            await d.__aenter__()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close all underlying downloaders."""
        for d in self._downloaders:
            await d.__aexit__(*args)
        await super().__aexit__(*args)

    async def download(self, doi: str) -> bytes | None:
        """Try each downloader in order until one succeeds.

        Args:
            doi: The DOI of the paper to download.

        Returns:
            PDF bytes if any downloader succeeds, None otherwise.
        """
        for downloader in self._downloaders:
            try:
                result = await downloader.download(doi)
                if result:
                    logger.debug("Downloaded %s via %s", doi, downloader.name)
                    return result
            except Exception as e:
                logger.debug("Downloader %s failed for %s: %s", downloader.name, doi, e)
                continue

        logger.debug("All downloaders failed for: %s", doi)
        return None
