# scimesh/download/__init__.py
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from pathlib import Path

from scimesh.download.base import Downloader
from scimesh.download.openaccess import OpenAccessDownloader
from scimesh.download.scihub import SciHubDownloader


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
) -> AsyncIterator[DownloadResult]:
    """Download papers for a list of DOIs.

    Tries each downloader in order until one succeeds. Saves PDFs to the
    output directory with sanitized filenames based on DOIs.

    Args:
        dois: An iterable of DOIs to download.
        output_dir: Directory to save downloaded PDFs.
        downloaders: Optional list of Downloader instances to use.
            Defaults to [OpenAccessDownloader(), SciHubDownloader()].

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

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    for doi in dois:
        result = await _download_single(doi, output_dir, downloaders)
        yield result


async def _download_single(
    doi: str,
    output_dir: Path,
    downloaders: list[Downloader],
) -> DownloadResult:
    """Download a single paper, trying each downloader in order.

    Args:
        doi: The DOI to download.
        output_dir: Directory to save the PDF.
        downloaders: List of downloaders to try.

    Returns:
        DownloadResult indicating success or failure.
    """
    filename = make_filename(doi) + ".pdf"
    filepath = output_dir / filename

    for downloader in downloaders:
        try:
            async with downloader:
                pdf_bytes = await downloader.download(doi)
                if pdf_bytes is not None:
                    filepath.write_bytes(pdf_bytes)
                    return DownloadResult(
                        doi=doi,
                        success=True,
                        filename=filename,
                        source=downloader.name,
                    )
        except Exception:
            # Continue to next downloader on error
            continue

    return DownloadResult(
        doi=doi,
        success=False,
        error=f"All downloaders failed for DOI: {doi}",
    )


__all__ = [
    "Downloader",
    "OpenAccessDownloader",
    "SciHubDownloader",
    "DownloadResult",
    "download_papers",
    "make_filename",
]
