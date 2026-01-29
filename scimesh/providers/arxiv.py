# scimesh/providers/arxiv.py
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from scimesh.models import Author, Paper
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
    remove_citation_range,
)

if TYPE_CHECKING:
    from scimesh.providers.openalex import OpenAlex

logger = logging.getLogger(__name__)

# arXiv API namespace
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
OPENSEARCH_NS = "{http://a9.com/-/spec/opensearch/1.1/}"


class Arxiv(Provider):
    """arXiv paper search provider."""

    name = "arxiv"
    BASE_URL = "https://export.arxiv.org/api/query"
    PAGE_SIZE = 100  # arXiv max per request
    RATE_LIMIT_DELAY = 3.0  # Required delay between requests (seconds)
    MAX_RESULTS = 30000  # arXiv hard limit

    def _load_from_env(self) -> str | None:
        return None  # arXiv doesn't require API key

    def _translate_query(self, query: Query) -> str:
        """Convert Query AST to arXiv search syntax."""
        match query:
            case Field(field="title", value=v):
                return f'ti:"{v}"'
            case Field(field="author", value=v):
                return f'au:"{v}"'
            case Field(field="abstract", value=v):
                return f'abs:"{v}"'
            case Field(field="keyword", value=v):
                return f'all:"{v}"'
            case Field(field="fulltext", value=v):
                return f'all:"{v}"'
            case Field(field="doi", value=v):
                return f'doi:"{v}"'
            case And(left=l, right=r):
                left_q = self._translate_query(l)
                right_q = self._translate_query(r)
                if isinstance(r, Not):
                    return f"({left_q} ANDNOT {self._translate_query(r.operand)})"
                if not left_q:
                    return right_q
                if not right_q:
                    return left_q
                return f"({left_q} AND {right_q})"
            case Or(left=l, right=r):
                left_q = self._translate_query(l)
                right_q = self._translate_query(r)
                return f"({left_q} OR {right_q})"
            case Not(operand=o):
                return f"ANDNOT {self._translate_query(o)}"
            case YearRange():
                return ""  # arXiv doesn't support year filter in query
            case CitationRange():
                return ""  # arXiv doesn't have citation data
            case _:
                raise ValueError(f"Unsupported query node: {query}")

    ENRICHMENT_BATCH_SIZE = 50

    async def search(
        self,
        query: Query,
    ) -> AsyncIterator[Paper]:
        """Search arXiv and yield papers."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # Extract citation filter - arXiv has no citation data natively
        citation_filter = extract_citation_range(query)
        query_without_citations = remove_citation_range(query)

        if query_without_citations is None:
            logger.warning(
                "arXiv does not provide citation data; citation-only queries return no results"
            )
            return

        if citation_filter is None:
            # No citation filter: normal search
            async for paper in self._search_raw(query_without_citations):
                yield paper
        else:
            # With citation filter: enrich via OpenAlex
            logger.info("Enriching arXiv results with citation data from OpenAlex")
            from scimesh.providers.openalex import OpenAlex
            from scimesh.search import chunked

            async with OpenAlex() as openalex:
                raw_stream = self._search_raw(query_without_citations)
                async for batch in chunked(raw_stream, self.ENRICHMENT_BATCH_SIZE, timeout=5.0):
                    citations = await self._fetch_citations_batch(openalex, batch)
                    for paper in batch:
                        enriched = self._with_citations(paper, citations)
                        if self._passes_citation_filter(enriched, citation_filter):
                            yield enriched

    async def _search_raw(self, query: Query) -> AsyncIterator[Paper]:
        """Raw arXiv search without citation enrichment."""
        if self._client is None:
            raise RuntimeError("Provider not initialized")

        query_str = self._translate_query(query)
        logger.debug("Translated query: %s", query_str)
        if not query_str:
            logger.debug("Empty query, returning no results")
            return

        year_filter = self._extract_year_filter(query)
        start = 0
        is_first_request = True

        while True:
            if start >= self.MAX_RESULTS:
                logger.debug("Reached arXiv hard limit of %d results", self.MAX_RESULTS)
                break

            if not is_first_request:
                await asyncio.sleep(self.RATE_LIMIT_DELAY)
            is_first_request = False

            params = {
                "search_query": query_str,
                "start": start,
                "max_results": self.PAGE_SIZE,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }

            url = f"{self.BASE_URL}?{urlencode(params)}"
            logger.debug("Requesting: %s", url)
            response = await self._client.get(url)
            response.raise_for_status()
            logger.debug("Response status: %s", response.status_code)

            root = ET.fromstring(response.text)

            total_results_el = root.find(f"{OPENSEARCH_NS}totalResults")
            total_results = (
                int(total_results_el.text)
                if total_results_el is not None and total_results_el.text
                else 0
            )
            logger.debug("Total results: %d, start: %d", total_results, start)

            entries = root.findall(f"{ATOM_NS}entry")
            entries_count = len(entries)

            for entry in entries:
                paper = self._parse_entry(entry)
                if paper and self._matches_year_filter(paper, year_filter):
                    yield paper

            start += self.PAGE_SIZE

            if start >= total_results or entries_count < self.PAGE_SIZE:
                break

    async def _fetch_citations_batch(
        self,
        openalex: OpenAlex,
        papers: list[Paper],
    ) -> dict[str, int]:
        """Fetch citation counts from OpenAlex for arXiv papers."""
        arxiv_ids = []
        for p in papers:
            aid = p.extras.get("arxiv_id")
            if aid:
                # Remove version suffix (e.g., 1706.03762v5 -> 1706.03762)
                arxiv_ids.append(aid.split("v")[0] if "v" in aid else aid)

        if not arxiv_ids:
            return {}

        dois = "|".join(f"10.48550/arXiv.{aid}" for aid in arxiv_ids)
        url = f"{openalex.BASE_URL}?filter=doi:{dois}&select=ids,cited_by_count&per_page=200"
        logger.debug("Fetching citations from OpenAlex: %s", url)

        if openalex._client is None:
            return {}
        response = await openalex._client.get(url)
        response.raise_for_status()
        data = response.json()

        result: dict[str, int] = {}
        for work in data.get("results", []):
            # Use ids.doi which preserves the original arXiv DOI
            ids = work.get("ids", {})
            doi = ids.get("doi", "").replace("https://doi.org/", "")
            # Extract arxiv_id from DOI: 10.48550/arXiv.1706.03762 -> 1706.03762
            match = re.search(r"arxiv\.(\d+\.\d+)", doi, re.IGNORECASE)
            if match:
                arxiv_id = match.group(1)
                if (count := work.get("cited_by_count")) is not None:
                    result[arxiv_id] = count
        return result

    def _with_citations(self, paper: Paper, citations: dict[str, int]) -> Paper:
        """Return paper with citations_count from lookup."""
        arxiv_id = paper.extras.get("arxiv_id", "")
        arxiv_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
        if arxiv_id in citations:
            return replace(paper, citations_count=citations[arxiv_id])
        return paper

    def _passes_citation_filter(self, paper: Paper, f: CitationRange) -> bool:
        """Check if paper passes citation filter."""
        if paper.citations_count is None:
            return False
        if f.min is not None and paper.citations_count < f.min:
            return False
        if f.max is not None and paper.citations_count > f.max:
            return False
        return True

    def _extract_year_filter(self, query: Query) -> YearRange | None:
        """Extract YearRange from query if present."""
        match query:
            case YearRange() as yr:
                return yr
            case And(left=l, right=r):
                return self._extract_year_filter(l) or self._extract_year_filter(r)
            case Or(left=l, right=r):
                return self._extract_year_filter(l) or self._extract_year_filter(r)
            case _:
                return None

    def _matches_year_filter(self, paper: Paper, year_filter: YearRange | None) -> bool:
        """Check if paper matches year filter."""
        if year_filter is None:
            return True
        if year_filter.start and paper.year < year_filter.start:
            return False
        if year_filter.end and paper.year > year_filter.end:
            return False
        return True

    def _parse_entry(self, entry: ET.Element) -> Paper | None:
        """Parse an arXiv entry XML element into a Paper."""
        title_el = entry.find(f"{ATOM_NS}title")
        if title_el is None or not title_el.text:
            return None

        title = " ".join(title_el.text.split())

        # Authors
        authors = []
        for author_el in entry.findall(f"{ATOM_NS}author"):
            name_el = author_el.find(f"{ATOM_NS}name")
            if name_el is not None and name_el.text:
                affil_el = author_el.find(f"{ARXIV_NS}affiliation")
                authors.append(
                    Author(
                        name=name_el.text,
                        affiliation=affil_el.text if affil_el is not None else None,
                    )
                )

        # Abstract
        summary_el = entry.find(f"{ATOM_NS}summary")
        abstract = (
            " ".join(summary_el.text.split())
            if summary_el is not None and summary_el.text
            else None
        )

        # Published date
        published_el = entry.find(f"{ATOM_NS}published")
        pub_date = None
        year = 0
        if published_el is not None and published_el.text:
            try:
                pub_date = datetime.fromisoformat(published_el.text.replace("Z", "+00:00")).date()
                year = pub_date.year
            except ValueError:
                pass

        # URL
        url = None
        for link in entry.findall(f"{ATOM_NS}link"):
            if link.get("type") == "text/html":
                url = link.get("href")
                break
        if not url:
            id_el = entry.find(f"{ATOM_NS}id")
            url = id_el.text if id_el is not None else None

        # DOI
        doi_el = entry.find(f"{ARXIV_NS}doi")
        doi = doi_el.text if doi_el is not None else None

        # Categories as topics
        categories = []
        for cat in entry.findall(f"{ARXIV_NS}primary_category"):
            term = cat.get("term")
            if term:
                categories.append(term)
        for cat in entry.findall(f"{ATOM_NS}category"):
            term = cat.get("term")
            if term and term not in categories:
                categories.append(term)

        # arXiv ID in extras
        arxiv_id = None
        id_el = entry.find(f"{ATOM_NS}id")
        if id_el is not None and id_el.text:
            arxiv_id = id_el.text.split("/abs/")[-1]

        # PDF URL (arXiv is always open access)
        pdf_url = None
        if arxiv_id:
            # Remove version suffix for consistent PDF URL
            base_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
            pdf_url = f"https://arxiv.org/pdf/{base_id}.pdf"

        return Paper(
            title=title,
            authors=tuple(authors),
            year=year,
            source="arxiv",
            abstract=abstract,
            doi=doi,
            url=url,
            topics=tuple(categories),
            publication_date=pub_date,
            pdf_url=pdf_url,
            open_access=True,  # arXiv is always open access
            extras={"arxiv_id": arxiv_id} if arxiv_id else {},
        )

    async def get(self, paper_id: str) -> Paper | None:
        """Fetch a specific paper by arXiv ID.

        Args:
            paper_id: arXiv ID (e.g., "1908.06954" or "1908.06954v2")
                or arXiv DOI (e.g., "10.48550/arXiv.1908.06954").

        Returns:
            Paper if found, None otherwise.
        """
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # Extract arXiv ID from DOI if needed
        arxiv_id = paper_id
        if paper_id.startswith("10.48550/arXiv."):
            arxiv_id = paper_id.replace("10.48550/arXiv.", "")
        elif paper_id.startswith("10.48550/"):
            arxiv_id = paper_id.replace("10.48550/", "")

        url = f"{self.BASE_URL}?id_list={arxiv_id}"
        logger.debug("Fetching: %s", url)

        response = await self._client.get(url)
        response.raise_for_status()

        root = ET.fromstring(response.text)

        # Check if there are any results
        entries = root.findall(f"{ATOM_NS}entry")
        if not entries:
            return None

        # Parse the first (and should be only) entry
        entry = entries[0]

        # Check for error (arXiv returns an entry even for invalid IDs)
        # but with "Error" in the title
        title_el = entry.find(f"{ATOM_NS}title")
        if title_el is not None and title_el.text and "Error" in title_el.text:
            return None

        return self._parse_entry(entry)
