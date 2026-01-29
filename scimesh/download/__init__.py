# scimesh/download/__init__.py
import logging
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx

from scimesh.cache import PaperCache
from scimesh.download.base import Downloader
from scimesh.download.fallback import FallbackDownloader
from scimesh.download.host_concurrency import HostSemaphores
from scimesh.download.openaccess import OpenAccessDownloader
from scimesh.download.scihub import SciHubDownloader

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Result of a paper download attempt."""

    doi: str
    success: bool
    filename: str | None = None
    source: str | None = None  # "open_access" | "scihub"
    error: str | None = None


def make_filename(doi: str) -> str:
    """Sanitize DOI to create a valid filename.

    Replaces invalid filesystem characters with safe alternatives.

    Args:
        doi: The DOI to sanitize.

    Returns:
        A sanitized filename (without .pdf extension).

    Example:
        >>> make_filename("10.1234/paper.v1")
        '10.1234_paper.v1'
    """
    # Replace / with _
    filename = doi.replace("/", "_")

    # Replace other invalid characters: \ : * ? " < > |
    invalid_chars = r'[\\:*?"<>|]'
    filename = re.sub(invalid_chars, "_", filename)

    return filename


async def download_papers(
    dois: Iterable[str],
    output_dir: Path,
    downloaders: list[Downloader] | None = None,
    cache: PaperCache | None = None,
    use_cache: bool = True,
) -> AsyncIterator[DownloadResult]:
    """Download papers for a list of DOIs.

    Tries each downloader in order until one succeeds. Saves PDFs to the
    output directory with sanitized filenames based on DOIs.

    If caching is enabled, checks the cache before downloading and saves
    successfully downloaded PDFs to the cache.

    Args:
        dois: An iterable of DOIs to download.
        output_dir: Directory to save downloaded PDFs.
        downloaders: Optional list of Downloader instances to use.
            Defaults to [OpenAccessDownloader(), SciHubDownloader()].
        cache: Optional PaperCache instance. If None and use_cache is True,
            a default cache is created.
        use_cache: Whether to use caching. Defaults to True.

    Yields:
        DownloadResult for each DOI, indicating success or failure.

    Example:
        async for result in download_papers(["10.1234/paper"], Path("./pdfs")):
            if result.success:
                print(f"Downloaded: {result.filename}")
            else:
                print(f"Failed: {result.error}")
    """
    if downloaders is None:
        downloaders = [OpenAccessDownloader()]

    # Initialize cache if caching is enabled
    if use_cache and cache is None:
        cache = PaperCache()

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    for doi in dois:
        result = await _download_single(doi, output_dir, downloaders, cache if use_cache else None)
        yield result


async def _download_single(
    doi: str,
    output_dir: Path,
    downloaders: list[Downloader],
    cache: PaperCache | None = None,
) -> DownloadResult:
    """Download a single paper, trying each downloader in order.

    If a cache is provided, checks the cache first and saves successful
    downloads to the cache.

    Args:
        doi: The DOI to download.
        output_dir: Directory to save the PDF.
        downloaders: List of downloaders to try.
        cache: Optional PaperCache for caching PDFs.

    Returns:
        DownloadResult indicating success or failure.
    """
    filename = make_filename(doi) + ".pdf"
    filepath = output_dir / filename

    # Check cache first
    if cache is not None:
        cached_path = cache.get_pdf_path(doi)
        if cached_path is not None:
            # Copy from cache to output directory
            pdf_bytes = cached_path.read_bytes()
            filepath.write_bytes(pdf_bytes)
            return DownloadResult(
                doi=doi,
                success=True,
                filename=filename,
                source="cache",
            )

    for downloader in downloaders:
        try:
            async with downloader:
                pdf_bytes = await downloader.download(doi)
                if pdf_bytes is not None:
                    filepath.write_bytes(pdf_bytes)
                    # Save to cache after successful download
                    if cache is not None:
                        cache.save_pdf(doi, pdf_bytes)
                    return DownloadResult(
                        doi=doi,
                        success=True,
                        filename=filename,
                        source=downloader.name,
                    )
        except httpx.TimeoutException:
            logger.debug("Timeout from %s for DOI %s", downloader.name, doi)
            continue
        except httpx.HTTPStatusError as e:
            logger.debug("HTTP %s from %s for DOI %s", e.response.status_code, downloader.name, doi)
            continue
        except httpx.RequestError as e:
            logger.debug("Request error from %s for DOI %s: %s", downloader.name, doi, e)
            continue
        except Exception as e:
            logger.warning("Unexpected error from %s for DOI %s: %s", downloader.name, doi, e)
            continue

    return DownloadResult(
        doi=doi,
        success=False,
        error=f"All downloaders failed for DOI: {doi}",
    )


__all__ = [
    "Downloader",
    "FallbackDownloader",
    "HostSemaphores",
    "OpenAccessDownloader",
    "SciHubDownloader",
    "DownloadResult",
    "PaperCache",
    "download_papers",
    "make_filename",
]
