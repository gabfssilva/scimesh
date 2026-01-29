# scimesh/providers/_fulltext_fallback.py
"""Mixin that provides local FTS5 fallback for providers without native fulltext."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from scimesh.cache import PaperCache
from scimesh.fulltext import FulltextIndex, extract_text_from_pdf
from scimesh.models import Paper
from scimesh.query.combinators import Query, extract_fulltext_term, remove_fulltext

if TYPE_CHECKING:
    from scimesh.download.base import Downloader

logger = logging.getLogger(__name__)


class FulltextFallbackMixin:
    """Mixin that provides local FTS5 fallback for providers without native fulltext.

    Providers that inherit from this mixin should:
    1. Move their search logic to _search_api()
    2. In search(), check has_fulltext() and call _search_with_fulltext_filter() if true

    Attributes:
        _downloader: Optional downloader for auto-downloading papers during fulltext
            search. If provided, papers not in the local index will be downloaded,
            text extracted, and indexed. Default: None (no auto-download).
    """

    _downloader: Downloader | None = None

    async def _search_with_fulltext_filter(
        self,
        query: Query,
    ) -> AsyncIterator[Paper]:
        """Search with fulltext filtering using local FTS5 index.

        This method:
        1. Extracts the fulltext term from the query
        2. Gets pre-indexed matches from local FTS5 index
        3. Streams results from API with base query (fulltext removed)
        4. For pre-indexed papers: yields immediately if they match
        5. For non-indexed papers (if downloader configured):
           - Downloads PDF, extracts text, indexes
           - Yields paper if it matches the fulltext term

        Args:
            query: The query containing a fulltext field.

        Yields:
            Paper instances that match the fulltext term.
        """
        term = extract_fulltext_term(query)
        if not term:
            return

        # Remove fulltext from query to get the base query
        base_query = remove_fulltext(query)
        if base_query is None:
            logger.warning(
                "Fulltext search requires additional filters for providers without "
                "native fulltext support. Add TITLE(), AUTHOR(), or other filters. "
                "Example: ALL(term) AND TITLE(topic)"
            )
            return

        index = FulltextIndex()
        downloader = self._downloader
        cache = PaperCache() if downloader else None

        # Get pre-indexed matches from local FTS5 index
        pre_indexed = set(index.search(term, limit=10000))

        if pre_indexed:
            logger.debug("Found %d papers in local index matching: %s", len(pre_indexed), term)
        else:
            logger.debug("No papers in local index match fulltext term: %s", term)

        try:
            if downloader:
                await downloader.__aenter__()

            # Stream from API
            async for paper in self._search_api(base_query):  # type: ignore[attr-defined]
                paper_id = paper.doi or paper.extras.get("paper_id")

                # Pre-indexed paper that matches → yield immediately
                if paper_id and paper_id in pre_indexed:
                    yield paper
                    continue

                # No downloader or no DOI → skip
                if not downloader or not paper.doi or cache is None:
                    continue

                # Download, extract, index, check match → yield if matches
                text = await self._try_download_single(paper.doi, downloader, cache, index)
                if text and self._text_matches_term(text, term):
                    yield paper
        finally:
            if downloader:
                await downloader.__aexit__(None, None, None)

    async def _try_download_single(
        self,
        doi: str,
        downloader: Downloader,
        cache: PaperCache,
        index: FulltextIndex,
    ) -> str | None:
        """Try to download and extract text from a single paper.

        Args:
            doi: The DOI to download.
            downloader: Downloader instance to use (handles concurrency internally).
            cache: Paper cache for storing PDFs and text.
            index: Fulltext index for storing extracted text.

        Returns:
            Extracted text if successful, None otherwise.
        """
        # Already indexed? Return cached text
        if index.has(doi):
            return cache.get_text(doi)

        try:
            pdf_bytes = await downloader.download(doi)
            if pdf_bytes:
                pdf_path = cache.save_pdf(doi, pdf_bytes)
                text = extract_text_from_pdf(pdf_path)
                if text:
                    cache.save_text(doi, text)
                    index.add(doi, text)
                    logger.debug("Downloaded and indexed: %s", doi)
                    return text
        except Exception as e:
            logger.debug("Failed to download/extract %s: %s", doi, e)

        return None

    def _text_matches_term(self, text: str, term: str) -> bool:
        """Check if text contains the search term (case-insensitive).

        Args:
            text: The extracted text to search.
            term: The search term.

        Returns:
            True if the term is found in the text.
        """
        return term.lower() in text.lower()

    async def _search_api(
        self,
        query: Query,
    ) -> AsyncIterator[Paper]:
        """Execute the actual API search. Must be implemented by provider."""
        raise NotImplementedError("Provider must implement _search_api()")
        yield  # type: ignore  # pragma: no cover
