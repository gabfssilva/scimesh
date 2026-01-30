# scimesh/download/scihub.py
"""Sci-Hub downloader for scientific papers."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import httpx

from scimesh.download.base import Downloader

if TYPE_CHECKING:
    from scimesh.download.host_concurrency import HostSemaphores

logger = logging.getLogger(__name__)


class SciHubDownloader(Downloader):
    """Downloader that uses Sci-Hub to fetch PDFs.

    Sci-Hub domains change frequently, so this downloader tries
    multiple known domains in order until one succeeds.

    Hosts accessed:
        - sci-hub.se, sci-hub.st, sci-hub.ru (HTML page + PDF download)
    """

    name = "scihub"

    # Known Sci-Hub domains - these may need updating as domains change
    domains = [
        "sci-hub.se",
        "sci-hub.st",
        "sci-hub.ru",
    ]

    def __init__(self, host_semaphores: HostSemaphores | None = None):
        """Initialize the Sci-Hub downloader.

        Args:
            host_semaphores: Shared per-host semaphores for concurrency control.
        """
        super().__init__(host_semaphores=host_semaphores)

    def _extract_pdf_url(self, html: str) -> str | None:
        """Extract PDF URL from Sci-Hub HTML response.

        Looks for <embed> or <iframe> tags containing .pdf URLs.

        Args:
            html: The HTML content to parse.

        Returns:
            The PDF URL if found, None otherwise.
        """
        # Look for embed, iframe, object tags, or download links containing PDF URLs
        # Patterns handle optional spaces around = (SciHub uses "data = " with spaces)
        patterns = [
            r'<object[^>]+data\s*=\s*["\']([^"\']*\.pdf[^"\']*)["\']',
            r'href\s*=\s*["\']([^"\']*download[^"\']*\.pdf)["\']',
            r'<embed[^>]+src\s*=\s*["\']([^"\']*\.pdf[^"\']*)["\']',
            r'<iframe[^>]+src\s*=\s*["\']([^"\']*\.pdf[^"\']*)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                url = match.group(1)
                # Handle protocol-relative URLs (starting with //)
                if url.startswith("//"):
                    url = "https:" + url
                return url

        return None

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make an HTTP GET request with per-host concurrency control.

        Args:
            url: The URL to fetch.
            **kwargs: Additional arguments for httpx.get().

        Returns:
            The HTTP response.
        """
        if self._client is None:
            raise RuntimeError("Downloader must be used as async context manager")

        if self._host_semaphores:
            async with self._host_semaphores.acquire(url):
                return await self._client.get(url, **kwargs)
        return await self._client.get(url, **kwargs)

    async def _attempt_download(self, doi: str, domain: str) -> bytes | None:
        """Attempt to download PDF from a specific Sci-Hub domain.

        Args:
            doi: The DOI of the paper.
            domain: The Sci-Hub domain to try.

        Returns:
            PDF bytes if successful, None otherwise.
        """
        if self._client is None:
            raise RuntimeError("Downloader must be used as async context manager")

        try:
            # Construct Sci-Hub URL
            url = f"https://{domain}/{doi}"
            response = await self._get(url, follow_redirects=True)

            if response.status_code != 200:
                return None

            # Extract PDF URL from HTML
            pdf_url = self._extract_pdf_url(response.text)
            if not pdf_url:
                # Log first 500 chars to debug what SciHub returned
                preview = response.text[:500].replace("\n", " ")
                logger.debug("  [SciHub] No PDF URL in HTML from %s: %s...", domain, preview)
                return None

            # Handle relative URLs (starting with /)
            if pdf_url.startswith("/"):
                pdf_url = f"https://{domain}{pdf_url}"

            # Download the PDF
            pdf_response = await self._get(pdf_url, follow_redirects=True)
            if pdf_response.status_code == 200:
                return pdf_response.content

        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.debug("  [SciHub] Connection error for %s: %s", domain, e)
            return None

        return None

    async def download(self, doi: str) -> bytes | None:
        """Download PDF for the given DOI from Sci-Hub.

        Tries multiple Sci-Hub domains in order until one succeeds.

        Args:
            doi: The DOI of the paper to download.

        Returns:
            PDF bytes if found, None otherwise.
        """
        if self._client is None:
            raise RuntimeError("Downloader must be used as async context manager")

        logger.info("  [SciHub] Trying DOI: %s", doi)
        for domain in self.domains:
            result = await self._attempt_download(doi, domain)
            if result is not None:
                logger.info("  [SciHub] Success via %s", domain)
                return result
            logger.debug("  [SciHub] Failed via %s", domain)

        logger.info("  [SciHub] All domains failed for: %s", doi)
        return None
