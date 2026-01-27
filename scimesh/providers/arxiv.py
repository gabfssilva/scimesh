# scimesh/providers/arxiv.py
import logging
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from datetime import datetime
from urllib.parse import urlencode

from scimesh.models import Author, Paper
from scimesh.providers.base import Provider
from scimesh.query.combinators import And, Field, Not, Or, Query, YearRange

logger = logging.getLogger(__name__)

# arXiv API namespace
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class Arxiv(Provider):
    """arXiv paper search provider."""

    name = "arxiv"
    BASE_URL = "https://export.arxiv.org/api/query"

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
            case _:
                raise ValueError(f"Unsupported query node: {query}")

    async def search(
        self,
        query: Query,
    ) -> AsyncIterator[Paper]:
        """Search arXiv and yield papers."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        query_str = self._translate_query(query)
        logger.debug("Translated query: %s", query_str)
        if not query_str:
            logger.debug("Empty query, returning no results")
            return

        params = {
            "search_query": query_str,
            "start": 0,
            "max_results": 100,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.debug("Requesting: %s", url)
        response = await self._client.get(url)
        response.raise_for_status()
        logger.debug("Response status: %s", response.status_code)

        # Filter by year if YearRange is in query
        year_filter = self._extract_year_filter(query)

        root = ET.fromstring(response.text)
        for entry in root.findall(f"{ATOM_NS}entry"):
            paper = self._parse_entry(entry)
            if paper and self._matches_year_filter(paper, year_filter):
                yield paper

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
