# scimesh/download/throttle.py
"""Per-host concurrency control for downloaders."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse


class HostSemaphores:
    """Manages per-host semaphores for concurrency control.

    This allows fine-grained control over how many concurrent requests
    are made to each host, regardless of which downloader is making the request.

    Example:
        >>> # Default limit for all hosts
        >>> semaphores = HostSemaphores(default=3)
        >>>
        >>> # Per-host limits
        >>> semaphores = HostSemaphores({
        ...     "arxiv.org": 2,       # max 2 concurrent to arXiv
        ...     "api.unpaywall.org": 3,  # max 3 concurrent to Unpaywall
        ...     "sci-hub.se": 2,      # max 2 concurrent to Sci-Hub
        ... })
        >>>
        >>> # Both: default with per-host overrides
        >>> semaphores = HostSemaphores({"arxiv.org": 2}, default=5)
        >>>
        >>> # Multiple downloaders can share the same semaphores
        >>> open_access = OpenAccessDownloader(host_semaphores=semaphores)
        >>> scihub = SciHubDownloader(host_semaphores=semaphores)
    """

    def __init__(
        self,
        limits: dict[str, int] | None = None,
        default: int | None = None,
    ):
        """Initialize with per-host concurrency limits.

        Args:
            limits: Dictionary mapping hostnames to their concurrency limits.
            default: Default concurrency limit for hosts not in limits dict.
                If None, unlisted hosts have no limit. Default: None.
        """
        self._limits = limits or {}
        self._default = default
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _get_semaphore(self, host: str) -> asyncio.Semaphore | None:
        """Get or create semaphore for a host."""
        # Check explicit limit first, then default
        limit = self._limits.get(host) or self._default
        if limit is None:
            return None

        if host not in self._semaphores:
            self._semaphores[host] = asyncio.Semaphore(limit)

        return self._semaphores[host]

    @asynccontextmanager
    async def acquire(self, url: str) -> AsyncIterator[None]:
        """Acquire semaphore for the given URL's host.

        Args:
            url: The URL being accessed. The host is extracted automatically.

        Yields:
            None. The semaphore is held for the duration of the context.
        """
        host = urlparse(url).netloc
        semaphore = self._get_semaphore(host)

        if semaphore:
            async with semaphore:
                yield
        else:
            yield

    @asynccontextmanager
    async def acquire_host(self, host: str) -> AsyncIterator[None]:
        """Acquire semaphore for a specific host.

        Args:
            host: The hostname (e.g., "arxiv.org").

        Yields:
            None. The semaphore is held for the duration of the context.
        """
        semaphore = self._get_semaphore(host)

        if semaphore:
            async with semaphore:
                yield
        else:
            yield

    def get_limit(self, host: str) -> int | None:
        """Get the concurrency limit for a host.

        Args:
            host: The hostname to check.

        Returns:
            The limit if configured (explicit or default), None otherwise.
        """
        return self._limits.get(host) or self._default

    def set_limit(self, host: str, limit: int) -> None:
        """Set or update the concurrency limit for a host.

        Args:
            host: The hostname.
            limit: The maximum concurrent requests.
        """
        self._limits[host] = limit
        # Clear existing semaphore so it gets recreated with new limit
        self._semaphores.pop(host, None)
