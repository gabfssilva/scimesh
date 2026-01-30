# scimesh/download/base.py
"""Base class for paper downloaders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Self

import httpx

if TYPE_CHECKING:
    from scimesh.download.host_concurrency import HostSemaphores


class Downloader(ABC):
    """Base class for paper downloaders.

    Downloaders can use HostSemaphores for per-host concurrency control,
    allowing fine-grained limits on concurrent requests to each service.

    Example:
        >>> semaphores = HostSemaphores({
        ...     "arxiv.org": 2,
        ...     "api.unpaywall.org": 3,
        ... })
        >>> open_access = OpenAccessDownloader(host_semaphores=semaphores)
        >>> scihub = SciHubDownloader(host_semaphores=semaphores)
        >>> # Both share the same semaphores - arXiv limited to 2 concurrent
    """

    name: str

    def __init__(self, host_semaphores: HostSemaphores | None = None) -> None:
        """Initialize the downloader.

        Args:
            host_semaphores: Shared per-host semaphores for concurrency control.
                If None, no concurrency limits are applied. Default: None.
        """
        self._client: httpx.AsyncClient | None = None
        self._host_semaphores = host_semaphores

    @abstractmethod
    async def download(self, doi: str) -> bytes | None:
        """Download PDF for the given DOI.

        Args:
            doi: The DOI of the paper to download.

        Returns:
            PDF bytes if found, None otherwise.
        """
        ...

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
