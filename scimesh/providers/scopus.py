import logging
import os
from collections.abc import AsyncIterator
from datetime import date
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse

import streamish as st

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

logger = logging.getLogger(__name__)


class Scopus(Provider):
    """Scopus paper search provider."""

    name = "scopus"
    BASE_URL = "https://api.elsevier.com/content/search/scopus"
    PAGE_SIZE = 25

    def _load_from_env(self) -> str | None:
        return os.getenv("SCOPUS_API_KEY")

    def _translate_query(self, query: Query) -> str:
        """Convert Query AST to Scopus query syntax."""
        match query:
            case Field(field="title", value=v):
                return f"TITLE({v})"
            case Field(field="author", value=v):
                return f"AUTH({v})"
            case Field(field="abstract", value=v):
                return f"ABS({v})"
            case Field(field="keyword", value=v):
                return f"KEY({v})"
            case Field(field="fulltext", value=v):
                return f"ALL({v})"
            case Field(field="doi", value=v):
                return f"DOI({v})"
            case And(left=l, right=r):
                return f"({self._translate_query(l)} AND {self._translate_query(r)})"
            case Or(left=l, right=r):
                return f"({self._translate_query(l)} OR {self._translate_query(r)})"
            case Not(operand=o):
                return f"NOT {self._translate_query(o)}"
            case YearRange(start=s, end=e):
                if s and e:
                    if s == e:
                        return f"PUBYEAR = {s}"
                    else:
                        return f"(PUBYEAR > {s - 1} AND PUBYEAR < {e + 1})"
                elif s:
                    return f"PUBYEAR > {s - 1}"
                elif e:
                    return f"PUBYEAR < {e + 1}"
                return ""
            case CitationRange():
                return ""
            case _:
                raise ValueError(f"Unsupported query node: {query}")

    async def search(
        self,
        query: Query,
    ) -> AsyncIterator[Paper]:
        """Search Scopus and yield papers."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        if not self._api_key:
            raise ValueError("Scopus requires an API key. Set SCOPUS_API_KEY or pass api_key=")

        client = self._client

        citation_filter = extract_citation_range(query)
        query_without_citations = remove_citation_range(query)

        if query_without_citations is None:
            return

        query_str = self._translate_query(query_without_citations)
        logger.debug("Translated query: %s", query_str)

        headers = {
            "X-ELS-APIKey": self._api_key,
            "Accept": "application/json",
        }

        sort_param: str | None = None
        if citation_filter and citation_filter.min is not None:
            sort_param = "-citedby-count"
            logger.debug("Using sort=%s for citation filter optimization", sort_param)

        async def fetch_pages() -> AsyncIterator[list[dict]]:
            cursor: str | None = "*"

            while cursor is not None:
                params: dict[str, str | int] = {
                    "query": query_str,
                    "count": self.PAGE_SIZE,
                    "view": "COMPLETE",
                    "cursor": cursor,
                }
                if sort_param:
                    params["sort"] = sort_param

                url = f"{self.BASE_URL}?{urlencode(params)}"
                logger.debug("Requesting: %s", url)
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()
                search_results = data.get("search-results", {})
                results = search_results.get("entry", [])

                yield results

                cursor = self._extract_next_cursor(search_results)
                if len(results) < self.PAGE_SIZE:
                    break

        def passes_citation_filter(paper: Paper) -> bool:
            cit_count = paper.citations_count
            if citation_filter:
                if citation_filter.min is not None and (
                    cit_count is None or cit_count < citation_filter.min
                ):
                    return False
                if citation_filter.max is not None and (
                    cit_count is None or cit_count > citation_filter.max
                ):
                    return False
            return True

        stream = (
            st.stream(fetch_pages())
            .flat_map(lambda entries: entries)
            .map(self._parse_entry)
            .filter(lambda p: p is not None and passes_citation_filter(p))
        )
        async for paper in stream:
            if paper is not None:
                yield paper

    def _extract_next_cursor(self, search_results: dict) -> str | None:
        """Extract the next cursor from Scopus response links."""
        links = search_results.get("link", [])
        for link in links:
            if link.get("@ref") == "next":
                href = link.get("@href", "")
                if href:
                    parsed = urlparse(href)
                    query_params = parse_qs(parsed.query)
                    cursor_values = query_params.get("cursor", [])
                    if cursor_values:
                        return cursor_values[0]
        return None

    def _parse_entry(self, entry: dict) -> Paper | None:
        """Parse a Scopus entry into a Paper."""
        title = entry.get("dc:title")
        if not title:
            return None

        authors = []
        for author_data in entry.get("author", []):
            name = author_data.get("authname")
            if name:
                authors.append(Author(name=name))

        year = 0
        cover_date = entry.get("prism:coverDate", "")
        if cover_date:
            try:
                year = int(cover_date.split("-")[0])
            except (ValueError, IndexError):
                pass

        doi = entry.get("prism:doi")

        url = None
        for link in entry.get("link", []):
            if link.get("@ref") == "scopus":
                url = link.get("@href")
                break

        journal = entry.get("prism:publicationName")

        citations = None
        cited_by = entry.get("citedby-count")
        if cited_by:
            try:
                citations = int(cited_by)
            except ValueError:
                pass

        pub_date = None
        if cover_date:
            try:
                pub_date = date.fromisoformat(cover_date)
            except ValueError:
                pass

        topics = []
        subject_area = entry.get("subject-area", [])
        if isinstance(subject_area, list):
            for area in subject_area[:5]:
                if isinstance(area, dict):
                    topics.append(area.get("$", ""))

        is_oa = entry.get("openaccessFlag", False)

        pdf_url = None
        for link in entry.get("link", []):
            if link.get("@ref") == "full-text":
                pdf_url = link.get("@href")
                break

        return Paper(
            title=title,
            authors=tuple(authors),
            year=year,
            source="scopus",
            abstract=entry.get("dc:description"),
            doi=doi,
            url=url,
            topics=tuple(topics),
            citations_count=citations,
            publication_date=pub_date,
            journal=journal,
            pdf_url=pdf_url,
            open_access=is_oa,
            extras={"scopus_id": entry.get("dc:identifier")},
        )

    async def get(self, paper_id: str) -> Paper | None:
        """Fetch a specific paper by DOI or Scopus ID.

        Args:
            paper_id: DOI (e.g., "10.1038/nature14539") or Scopus ID.

        Returns:
            Paper if found, None otherwise.
        """
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        if not self._api_key:
            raise ValueError("Scopus requires an API key. Set SCOPUS_API_KEY or pass api_key=")

        if paper_id.startswith("SCOPUS_ID:"):
            scopus_id = paper_id.replace("SCOPUS_ID:", "")
            query_str = f"EID(2-s2.0-{scopus_id})"
        elif "/" in paper_id:
            query_str = f"DOI({paper_id})"
        else:
            query_str = f"EID(2-s2.0-{paper_id})"

        headers = {
            "X-ELS-APIKey": self._api_key,
            "Accept": "application/json",
        }

        params = {
            "query": query_str,
            "count": 1,
            "view": "COMPLETE",
        }

        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.debug("Fetching: %s", url)

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        results = data.get("search-results", {}).get("entry", [])

        if not results:
            return None

        if "error" in results[0]:
            return None

        return self._parse_entry(results[0])

    async def citations(
        self,
        paper_id: str,
        direction: Literal["in", "out", "both"] = "both",
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Get papers citing this paper.

        Note: Scopus API only supports getting papers that cite this paper (direction="in").
        For references (direction="out"), you need the Scopus Abstract API which requires
        different entitlements.

        Args:
            paper_id: DOI or Scopus ID.
            direction: Only "in" is supported (papers citing this one).
            max_results: Maximum number of results to return.

        Yields:
            Paper instances.
        """
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        if not self._api_key:
            raise ValueError("Scopus requires an API key. Set SCOPUS_API_KEY or pass api_key=")

        if direction == "out":
            logger.warning("Scopus does not support fetching references (direction='out')")
            return

        paper = await self.get(paper_id)
        if paper is None:
            return

        scopus_id = paper.extras.get("scopus_id")
        if not scopus_id:
            return

        if scopus_id.startswith("SCOPUS_ID:"):
            scopus_id = scopus_id.replace("SCOPUS_ID:", "")

        headers = {
            "X-ELS-APIKey": self._api_key,
            "Accept": "application/json",
        }

        params = {
            "query": f"REFEID(2-s2.0-{scopus_id})",
            "count": min(max_results, 25),
            "view": "COMPLETE",
        }

        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.debug("Fetching citing papers: %s", url)

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        results = data.get("search-results", {}).get("entry", [])

        for entry in results:
            if "error" in entry:
                continue
            parsed = self._parse_entry(entry)
            if parsed:
                yield parsed
