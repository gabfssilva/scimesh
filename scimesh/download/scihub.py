# scimesh/download/scihub.py
"""Sci-Hub downloader for scientific papers."""

import re

import httpx

from scimesh.download.base import Downloader
from scimesh.throttle import throttle


class SciHubDownloader(Downloader):
    """Downloader that uses Sci-Hub to fetch PDFs.

    Sci-Hub domains change frequently, so this downloader tries
    multiple known domains in order until one succeeds.
    """

    name = "scihub"

    # Known Sci-Hub domains - these may need updating as domains change
    domains = [
        "sci-hub.se",
        "sci-hub.st",
        "sci-hub.ru",
    ]

    def __init__(self):
        super().__init__()

    def _extract_pdf_url(self, html: str) -> str | None:
        """Extract PDF URL from Sci-Hub HTML response.

        Looks for <embed> or <iframe> tags containing .pdf URLs.

        Args:
            html: The HTML content to parse.

        Returns:
            The PDF URL if found, None otherwise.
        """
        # Look for embed or iframe tags with src containing .pdf
        # Pattern matches: src="..." or src='...'
        patterns = [
            r'<embed[^>]+src=["\']([^"\']*\.pdf[^"\']*)["\']',
            r'<iframe[^>]+src=["\']([^"\']*\.pdf[^"\']*)["\']',
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
            response = await self._client.get(url, follow_redirects=True)

            if response.status_code != 200:
                return None

            # Extract PDF URL from HTML
            pdf_url = self._extract_pdf_url(response.text)
            if not pdf_url:
                return None

            # Download the PDF
            pdf_response = await self._client.get(pdf_url, follow_redirects=True)
            if pdf_response.status_code == 200:
                return pdf_response.content

        except (httpx.RequestError, httpx.TimeoutException):
            return None

        return None

    @throttle(calls=1, period=3.0)
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

        for domain in self.domains:
            result = await self._attempt_download(doi, domain)
            if result is not None:
                return result

        return None
