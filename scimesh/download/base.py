# scimesh/download/base.py
"""Base class for paper downloaders."""

from abc import ABC, abstractmethod

import httpx


class Downloader(ABC):
    """Base class for paper downloaders."""

    name: str

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @abstractmethod
    async def download(self, doi: str) -> bytes | None:
        """Download PDF for the given DOI.

        Args:
            doi: The DOI of the paper to download.

        Returns:
            PDF bytes if found, None otherwise.
        """
        ...

    async def __aenter__(self) -> "Downloader":
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
