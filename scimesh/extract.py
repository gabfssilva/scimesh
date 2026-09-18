"""Text extraction from PDFs."""

from __future__ import annotations

import sys
from contextlib import redirect_stdout
from functools import cache
from importlib.metadata import version
from pathlib import Path


@cache
def extractor_version() -> str:
    """Tag stored alongside extracted text, so upgrades trigger re-extraction."""
    return f"pymupdf4llm/{version('pymupdf4llm')}"


def extract_markdown(pdf_path: Path) -> str:
    """Extract a PDF as markdown.

    Raises:
        Exception: Whatever PyMuPDF raises for unreadable or corrupt files.
    """
    # pymupdf4llm prints a banner to stdout on import, which would corrupt
    # piped CLI output.
    with redirect_stdout(sys.stderr):
        import pymupdf4llm

    markdown = pymupdf4llm.to_markdown(pdf_path)
    if not isinstance(markdown, str):
        raise TypeError(f"expected markdown text, got {type(markdown).__name__}")
    return markdown


__all__ = ["extract_markdown", "extractor_version"]
