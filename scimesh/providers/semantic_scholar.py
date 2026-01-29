# scimesh/providers/semantic_scholar.py
from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from datetime import date
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlencode

import httpx

from scimesh.models import Author, Paper
from scimesh.providers._fulltext_fallback import FulltextFallbackMixin
from scimesh.providers.base import Provider
from scimesh.query.combinators import (
    And,
    CitationRange,
    Field,
    Not,
    Or,
    Query,
    YearRange,
    extract_citation_range,
    has_fulltext,
    remove_citation_range,
)

if TYPE_CHECKING:
    from scimesh.download.base import Downloader

logger = logging.getLogger(__name__)

# API fields to request
API_FIELDS = (
    "paperId,title,abstract,authors,year,citationCount,referenceCount,"
    "venue,publicationDate,openAccessPdf,isOpenAccess,fieldsOfStudy,externalIds"
)


class SemanticScholar(FulltextFallbackMixin, Provider):
    """Semantic Scholar paper search provider."""

    name = "semantic_scholar"
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    PAGE_SIZE = 100  # Semantic Scholar max per request
    MAX_TOTAL_RESULTS = 1000  # Semantic Scholar relevance search limit

    def __init__(
        self,
        api_key: str | None = None,
        downloader: Downloader | None = None,
    ):
        super().__init__(api_key)
        self._downloader = downloader

    def _load_from_env(self) -> str | None:
        return os.getenv("SEMANTIC_SCHOLAR_API_KEY")

    def _translate_query(self, query: Query) -> tuple[str, int | None, int | None]:
        """Convert Query AST to Semantic Scholar query string and year range.

        Returns (query_string, year_start, year_end).
        Semantic Scholar uses a simple query string with optional year filter.
        """
        terms: list[str] = []
        year_start: int | None = None
        year_end: int | None = None

        year_start, year_end = self._collect_terms(query, terms)
        return (" ".join(terms), year_start, year_end)

    def _collect_terms(self, query: Query, terms: list[str]) -> tuple[int | None, int | None]:
        """Recursively collect search terms and year range from query AST.

        Returns (year_start, year_end) if found.
        """
        year_start: int | None = None
        year_end: int | None = None

        match query:
            case Field(field="title", value=v):
                # Semantic Scholar doesn't have field-specific search in basic API
                # Use quotes for phrase search
                terms.append(f'"{v}"')
            case Field(field="author", value=v):
                # Author search is not directly supported in query string
                # Include as regular terms
                terms.append(v)
            case Field(field="abstract", value=v):
                terms.append(v)
            case Field(field="keyword", value=v):
                terms.append(v)
            case Field(field="fulltext", value=v):
                terms.append(v)
            case Field(field="doi", value=v):
                # DOI search is handled differently but include for now
                terms.append(v)
            case And(left=l, right=r):
                ys1, ye1 = self._collect_terms(l, terms)
                ys2, ye2 = self._collect_terms(r, terms)
                year_start = ys1 or ys2
                year_end = ye1 or ye2
            case Or(left=l, right=r):
                # Semantic Scholar basic search doesn't support OR well
                # Just include both terms
                left_terms: list[str] = []
                right_terms: list[str] = []
                ys1, ye1 = self._collect_terms(l, left_terms)
                ys2, ye2 = self._collect_terms(r, right_terms)
                if left_terms and right_terms:
                    # Use | for OR in the query
                    terms.append(f"({' '.join(left_terms)} | {' '.join(right_terms)})")
                elif left_terms:
                    terms.extend(left_terms)
                elif right_terms:
                    terms.extend(right_terms)
                year_start = ys1 or ys2
                year_end = ye1 or ye2
            case Not(operand=o):
                # Semantic Scholar supports - for exclusion
                neg_terms: list[str] = []
                ys, ye = self._collect_terms(o, neg_terms)
                for term in neg_terms:
                    terms.append(f"-{term}")
                year_start = ys
                year_end = ye
            case YearRange(start=s, end=e):
                year_start = s
                year_end = e
            case CitationRange():
                pass  # Handled separately in _search_api

        return year_start, year_end

    async def search(
        self,
        query: Query,
    ) -> AsyncIterator[Paper]:
        """Search Semantic Scholar and yield papers."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # Use local fulltext fallback for fulltext queries
        if has_fulltext(query):
            async for paper in self._search_with_fulltext_filter(query):
                yield paper
            return

        async for paper in self._search_api(query):
            yield paper

    async def _fetch_with_retry(
        self,
        url: str,
        headers: dict[str, str],
    ) -> httpx.Response | None:
        """Fetch URL with retry logic for rate limiting (429)."""
        if self._client is None:
            return None

        max_retries = 3
        retry_delay = 1.0
        response: httpx.Response | None = None

        for attempt in range(max_retries):
            try:
                response = await self._client.get(url, headers=headers)

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        logger.warning(
                            "Rate limited (429), retrying in %.1f seconds (attempt %d/%d)",
                            retry_delay,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error("Rate limited after %d attempts", max_retries)
                        response.raise_for_status()

                response.raise_for_status()
                return response
            except httpx.HTTPStatusError:
                if attempt == max_retries - 1:
                    raise
                continue

        return None

    async def _search_api(
        self,
        query: Query,
    ) -> AsyncIterator[Paper]:
        """Execute the actual Semantic Scholar API search with pagination."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # Extract citation filter for native support + client-side max
        citation_filter = extract_citation_range(query)
        query_without_citations = remove_citation_range(query)

        if query_without_citations is None:
            logger.debug("Citation-only query, returning no results")
            return

        query_str, year_start, year_end = self._translate_query(query_without_citations)
        logger.debug("Translated query: %s", query_str)
        logger.debug("Year range: %s - %s", year_start, year_end)

        if not query_str:
            logger.debug("Empty query, returning no results")
            return

        params: dict[str, str | int] = {
            "query": query_str,
            "limit": self.PAGE_SIZE,
            "fields": API_FIELDS,
        }

        # Add citation filter (Semantic Scholar supports minCitationCount natively)
        if citation_filter and citation_filter.min is not None:
            params["minCitationCount"] = citation_filter.min

        # Add year filter if specified
        if year_start:
            params["year"] = f"{year_start}-" if not year_end else f"{year_start}-{year_end}"
        elif year_end:
            params["year"] = f"-{year_end}"

        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        # Pagination loop using offset
        offset = 0

        while offset < self.MAX_TOTAL_RESULTS:
            params["offset"] = offset
            url = f"{self.BASE_URL}?{urlencode(params)}"
            logger.debug("Requesting: %s", url)

            response = await self._fetch_with_retry(url, headers)
            if response is None:
                return

            logger.debug("Response status: %s", response.status_code)

            data = response.json()
            total = data.get("total", 0)
            results = data.get("data", [])
            logger.debug("Results count: %s, total: %s, offset: %s", len(results), total, offset)

            for paper_data in results:
                paper = self._parse_paper(paper_data)
                if paper:
                    # Apply client-side filter for max citations (API doesn't support it)
                    if (
                        citation_filter
                        and citation_filter.max is not None
                        and (
                            paper.citations_count is None
                            or paper.citations_count > citation_filter.max
                        )
                    ):
                        continue
                    yield paper

            # Check pagination termination conditions
            offset += self.PAGE_SIZE

            # Stop if: we've reached max results, exceeded total, or got a partial page
            if offset >= self.MAX_TOTAL_RESULTS or offset >= total or len(results) < self.PAGE_SIZE:
                break

    def _parse_paper(self, paper_data: dict) -> Paper | None:
        """Parse a Semantic Scholar paper response into a Paper."""
        title = paper_data.get("title")
        if not title:
            return None

        # Authors with affiliations
        authors = []
        for author_data in paper_data.get("authors", []):
            name = author_data.get("name")
            if name:
                # Semantic Scholar doesn't provide affiliations in basic search
                authors.append(Author(name=name))

        # Year
        year = paper_data.get("year") or 0

        # Abstract
        abstract = paper_data.get("abstract")

        # DOI from externalIds
        doi = None
        external_ids = paper_data.get("externalIds", {}) or {}
        if external_ids:
            doi = external_ids.get("DOI")

        # URL - construct from paperId
        paper_id = paper_data.get("paperId")
        url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None

        # Topics from fieldsOfStudy
        topics = []
        fields_of_study = paper_data.get("fieldsOfStudy") or []
        for field in fields_of_study[:5]:
            if field:
                topics.append(field)

        # Citations count
        citations_count = paper_data.get("citationCount")

        # References count
        references_count = paper_data.get("referenceCount")

        # Publication date
        pub_date = None
        pub_date_str = paper_data.get("publicationDate")
        if pub_date_str:
            try:
                pub_date = date.fromisoformat(pub_date_str)
            except ValueError:
                pass

        # Journal/venue
        journal = paper_data.get("venue")

        # Open access info
        is_oa = paper_data.get("isOpenAccess", False)

        # PDF URL from openAccessPdf
        pdf_url = None
        oa_pdf = paper_data.get("openAccessPdf")
        if oa_pdf and isinstance(oa_pdf, dict):
            pdf_url = oa_pdf.get("url")

        return Paper(
            title=title,
            authors=tuple(authors),
            year=year,
            source="semantic_scholar",
            abstract=abstract,
            doi=doi,
            url=url,
            topics=tuple(topics),
            citations_count=citations_count,
            publication_date=pub_date,
            journal=journal if journal else None,
            pdf_url=pdf_url,
            open_access=is_oa,
            references_count=references_count,
            extras={"semanticScholarId": paper_id} if paper_id else {},
        )

    async def get(self, paper_id: str) -> Paper | None:
        """Fetch a specific paper by DOI or Semantic Scholar ID.

        Args:
            paper_id: DOI (e.g., "10.1038/nature14539") or Semantic Scholar
                paper ID (40-character hex string).

        Returns:
            Paper if found, None otherwise.
        """
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # Semantic Scholar accepts DOI or paper ID directly
        # For DOI, we can search with DOI: prefix or just use the paper endpoint
        base_url = "https://api.semanticscholar.org/graph/v1/paper"

        # If it looks like a DOI (contains /), use DOI: prefix
        if "/" in paper_id and not paper_id.startswith("DOI:"):
            lookup_id = f"DOI:{paper_id}"
        else:
            lookup_id = paper_id

        url = f"{base_url}/{lookup_id}?fields={API_FIELDS}"

        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        logger.debug("Fetching: %s", url)

        # Retry logic for rate limiting
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await self._client.get(url, headers=headers)

                if response.status_code == 404:
                    return None

                if response.status_code == 429 and attempt < max_retries - 1:
                    logger.warning(
                        "Rate limited (429), retrying in %.1f seconds",
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue

                response.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                if attempt == max_retries - 1:
                    raise
                continue
        else:
            return None

        paper_data = response.json()
        return self._parse_paper(paper_data)

    async def citations(
        self,
        paper_id: str,
        direction: Literal["in", "out", "both"] = "both",
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Get papers citing this paper (in) or cited by this paper (out).

        Args:
            paper_id: DOI or Semantic Scholar paper ID.
            direction: "in" for papers citing this one, "out" for papers cited
                by this one, "both" for all.
            max_results: Maximum number of results to return.

        Yields:
            Paper instances.
        """
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # First get the paper to find its Semantic Scholar ID
        paper = await self.get(paper_id)
        if paper is None:
            return

        s2_id = paper.extras.get("semanticScholarId")
        if not s2_id:
            return

        base_url = "https://api.semanticscholar.org/graph/v1/paper"
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        count = 0

        # Get citing papers (papers that cite this one)
        if direction in ("in", "both"):
            url = f"{base_url}/{s2_id}/citations?fields={API_FIELDS}&limit={min(max_results, 1000)}"
            logger.debug("Fetching citations: %s", url)

            response = await self._client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
                    if count >= max_results:
                        return
                    citing_paper = item.get("citingPaper", {})
                    parsed = self._parse_paper(citing_paper)
                    if parsed:
                        yield parsed
                        count += 1

        # Get referenced papers (papers cited by this one)
        if direction in ("out", "both"):
            limit = min(max_results, 1000)
            url = f"{base_url}/{s2_id}/references?fields={API_FIELDS}&limit={limit}"
            logger.debug("Fetching references: %s", url)

            response = await self._client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
                    if count >= max_results:
                        return
                    cited_paper = item.get("citedPaper", {})
                    parsed = self._parse_paper(cited_paper)
                    if parsed:
                        yield parsed
                        count += 1
