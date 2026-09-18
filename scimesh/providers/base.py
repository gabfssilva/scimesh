"""Base class for paper search providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from typing import Literal, Self

import httpx

from scimesh._version import __version__
from scimesh.models import Paper
from scimesh.query.combinators import Query

USER_AGENT = f"scimesh/{__version__} (+https://github.com/gabfssilva/scimesh)"


class Provider(ABC):
    """Base class for paper search providers."""

    name: str
    supports_get: bool = False
    supports_citations: bool = False

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or self._load_from_env()
        self._client: httpx.AsyncClient | None = None
        self.transport_factory: Callable[[], httpx.AsyncBaseTransport] | None = None
        """Builds the transport for each open, so responses can be cached."""

    @abstractmethod
    def _load_from_env(self) -> str | None:
        """Load API key from environment variable."""
        ...

    def _auth_headers(self) -> dict[str, str]:
        """Headers that authenticate every request, when a key is configured."""
        return {}

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

        yield

    async def __aenter__(self) -> Self:
        # arXiv and OpenAlex both ask clients to identify themselves.
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": USER_AGENT, **self._auth_headers()},
            transport=self.transport_factory() if self.transport_factory else None,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
