# scimesh/providers/_fulltext_fallback.py
"""Mixin that provides local FTS5 fallback for providers without native fulltext."""

import logging
from collections.abc import AsyncIterator

from scimesh.fulltext import FulltextIndex
from scimesh.models import Paper
from scimesh.query.combinators import Query, extract_fulltext_term, remove_fulltext

logger = logging.getLogger(__name__)


class FulltextFallbackMixin:
    """Mixin that provides local FTS5 fallback for providers without native fulltext.

    Providers that inherit from this mixin should:
    1. Move their search logic to _search_api()
    2. In search(), check has_fulltext() and call _search_with_fulltext_filter() if true
    """

    async def _search_with_fulltext_filter(
        self,
        query: Query,
        max_results: int,
    ) -> AsyncIterator[Paper]:
        """Search with fulltext filtering using local FTS5 index.

        This method:
        1. Extracts the fulltext term from the query
        2. Removes fulltext from query and searches with remaining query
        3. Filters results to only include papers that match the fulltext term

        Args:
            query: The query containing a fulltext field.
            max_results: Maximum number of results to return.

        Yields:
            Paper instances that match the fulltext term.
        """
        term = extract_fulltext_term(query)
        if not term:
            return

        # Remove fulltext from query to get the base query
        base_query = remove_fulltext(query)
        if base_query is None:
            # Cannot search all papers from API - need at least one non-fulltext filter
            logger.warning(
                "Fulltext search requires additional filters for providers without "
                "native fulltext support. Add TITLE(), AUTHOR(), or other filters. "
                "Example: ALL(term) AND TITLE(topic)"
            )
            return

        # Get papers matching fulltext from local index
        index = FulltextIndex()
        matching_ids = set(index.search(term, limit=10000))  # Get all matches

        if not matching_ids:
            logger.debug("No papers in local index match fulltext term: %s", term)
            return

        logger.debug("Found %d papers in local index matching: %s", len(matching_ids), term)

        # Search with base query and filter by fulltext matches
        count = 0
        async for paper in self._search_api(base_query, max_results * 3):  # type: ignore
            if count >= max_results:
                return

            # Check if paper matches fulltext (by DOI or paper ID)
            paper_id = paper.doi or paper.extras.get("paper_id")
            if paper_id and paper_id in matching_ids:
                yield paper
                count += 1

    async def _search_api(
        self,
        query: Query,
        max_results: int,
    ) -> AsyncIterator[Paper]:
        """Execute the actual API search. Must be implemented by provider."""
        raise NotImplementedError("Provider must implement _search_api()")
        yield  # type: ignore  # pragma: no cover
