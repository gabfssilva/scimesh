# scimesh/download/openaccess.py
"""Open Access downloader using Unpaywall API."""

import json
import os

import httpx

from scimesh.download.base import Downloader


class OpenAccessDownloader(Downloader):
    """Downloader that uses Unpaywall API to find open access PDFs."""

    name = "open_access"

    def __init__(self):
        super().__init__()
        self.email = os.environ.get("UNPAYWALL_EMAIL")
        if not self.email:
            raise ValueError(
                "UNPAYWALL_EMAIL environment variable is required for OpenAccessDownloader"
            )

    def _unpaywall_url(self, doi: str) -> str:
        """Construct Unpaywall API URL for a given DOI."""
        return f"https://api.unpaywall.org/v2/{doi}?email={self.email}"

    def _extract_arxiv_id(self, doi: str) -> str | None:
        """Extract arXiv ID from an arXiv DOI.

        Args:
            doi: The DOI to extract arXiv ID from.

        Returns:
            arXiv ID if the DOI is an arXiv DOI, None otherwise.
        """
        arxiv_prefix = "10.48550/arxiv."
        if doi.lower().startswith(arxiv_prefix):
            return doi[len(arxiv_prefix) :]
        return None

    def _arxiv_pdf_url(self, arxiv_id: str) -> str:
        """Construct arXiv PDF URL for a given arXiv ID."""
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    async def download(self, doi: str) -> bytes | None:
        """Download PDF for the given DOI.

        Uses Unpaywall API to find open access PDF locations.
        Falls back to direct arXiv URL for arXiv DOIs.

        Args:
            doi: The DOI of the paper to download.

        Returns:
            PDF bytes if found, None otherwise.
        """
        if self._client is None:
            raise RuntimeError("Downloader must be used as async context manager")

        try:
            # Try Unpaywall first
            unpaywall_url = self._unpaywall_url(doi)
            response = await self._client.get(unpaywall_url)

            if response.status_code == 200:
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    return None

                oa_locations = data.get("oa_locations", [])

                # Try each OA location
                for location in oa_locations:
                    pdf_url = location.get("url_for_pdf")
                    if pdf_url:
                        pdf_response = await self._client.get(pdf_url, follow_redirects=True)
                        if pdf_response.status_code == 200:
                            return pdf_response.content

            # Fallback: try direct arXiv URL for arXiv DOIs
            arxiv_id = self._extract_arxiv_id(doi)
            if arxiv_id:
                arxiv_url = self._arxiv_pdf_url(arxiv_id)
                pdf_response = await self._client.get(arxiv_url, follow_redirects=True)
                if pdf_response.status_code == 200:
                    return pdf_response.content

        except httpx.RequestError:
            return None

        return None
