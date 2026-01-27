# scimesh/providers/base.py
"""Base class for paper search providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

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
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Execute search and yield papers."""
        ...

    async def __aenter__(self) -> "Provider":
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
