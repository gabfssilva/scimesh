"""Fallback-aware downloader that tries multiple downloaders in order."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from scimesh.download.base import Downloader, start_downloaders

if TYPE_CHECKING:
    from scimesh.download.host_concurrency import HostSemaphores

logger = logging.getLogger(__name__)


class FallbackDownloader(Downloader):
    """Downloader that tries multiple downloaders in order until one succeeds.

    Example:
        >>>
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
        self._stack = AsyncExitStack()
        self._started: list[Downloader] = []

    async def __aenter__(self) -> FallbackDownloader:
        """Open the underlying downloaders, skipping those that fail to start."""
        await super().__aenter__()
        self._started = await start_downloaders(self._stack, self._downloaders)
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the underlying downloaders that started."""
        await self._stack.aclose()
        self._started = []
        await super().__aexit__(*args)

    async def download(self, doi: str) -> bytes | None:
        """Try each downloader in order until one succeeds.

        Args:
            doi: The DOI of the paper to download.

        Returns:
            PDF bytes if any downloader succeeds, None otherwise.
        """
        for downloader in self._started:
            try:
                result = await downloader.download(doi)
                if result:
                    logger.debug("Downloaded %s via %s", doi, downloader.name)
                    return result
            except Exception as e:
                logger.warning("Downloader %s failed for %s: %s", downloader.name, doi, e)
                continue

        logger.debug("All downloaders failed for: %s", doi)
        return None
