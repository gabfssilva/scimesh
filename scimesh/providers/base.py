# scimesh/providers/base.py
"""Base class for paper search providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Literal, Self

import httpx

from scimesh.models import Paper
from scimesh.query.combinators import Query


class Provider(ABC):
    """Base class for paper search providers."""

    name: str

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or self._load_from_env()
        self._client: httpx.AsyncClient | None = None

    @abstractmethod
    def _load_from_env(self) -> str | None:
        """Load API key from environment variable."""
        ...

    @abstractmethod
    def search(
        self,
        query: Query,
    ) -> AsyncIterator[Paper]:
        """Execute search and yield papers."""
        ...

    async def get(self, paper_id: str) -> Paper | None:
        """Fetch a specific paper by DOI or provider-specific ID.

        Args:
            paper_id: DOI or provider-specific identifier.

        Returns:
            Paper if found, None otherwise.

        Note:
            Subclasses should override this method for better performance.
            Default implementation raises NotImplementedError.
        """
        raise NotImplementedError(f"{self.name} does not support get()")

    def citations(
        self,
        paper_id: str,
        direction: Literal["in", "out", "both"] = "both",
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Get papers citing this paper (in) or cited by this paper (out).

        Args:
            paper_id: DOI or provider-specific identifier.
            direction: "in" for papers citing this one, "out" for papers cited
                by this one, "both" for all (default).
            max_results: Maximum number of results to return.

        Yields:
            Paper instances.

        Note:
            Subclasses should override this method if they support citations.
            Default implementation raises NotImplementedError.
        """
        raise NotImplementedError(f"{self.name} does not support citations()")
        # The yield below is unreachable but required for type checking
        yield  # type: ignore  # pragma: no cover

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
