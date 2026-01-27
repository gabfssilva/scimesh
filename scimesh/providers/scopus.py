# scimesh/providers/scopus.py
import logging
import os
from collections.abc import AsyncIterator
from datetime import date
from urllib.parse import urlencode

from scimesh.models import Author, Paper
from scimesh.providers.base import Provider
from scimesh.query.combinators import And, Field, Not, Or, Query, YearRange

logger = logging.getLogger(__name__)


class Scopus(Provider):
    """Scopus paper search provider."""

    name = "scopus"
    BASE_URL = "https://api.elsevier.com/content/search/scopus"

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
            case _:
                raise ValueError(f"Unsupported query node: {query}")

    async def search(
        self,
        query: Query,
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Search Scopus and yield papers."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        if not self._api_key:
            raise ValueError("Scopus requires an API key. Set SCOPUS_API_KEY or pass api_key=")

        query_str = self._translate_query(query)
        logger.debug("Translated query: %s", query_str)

        headers = {
            "X-ELS-APIKey": self._api_key,
            "Accept": "application/json",
        }

        params = {
            "query": query_str,
            "count": min(max_results, 25),  # Scopus max per request with COMPLETE view
            "start": 0,
            "view": "COMPLETE",  # Required to get abstract (dc:description)
        }

        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.debug("Requesting: %s", url)
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        logger.debug("Response status: %s", response.status_code)

        data = response.json()
        results = data.get("search-results", {}).get("entry", [])
        logger.debug("Results count: %s", len(results))

        for entry in results:
            paper = self._parse_entry(entry)
            if paper:
                yield paper

    def _parse_entry(self, entry: dict) -> Paper | None:
        """Parse a Scopus entry into a Paper."""
        title = entry.get("dc:title")
        if not title:
            return None

        # Authors (Scopus returns "dc:creator" for first author only in search)
        authors = []
        creator = entry.get("dc:creator")
        if creator:
            authors.append(Author(name=creator))

        # Year
        year = 0
        cover_date = entry.get("prism:coverDate", "")
        if cover_date:
            try:
                year = int(cover_date.split("-")[0])
            except (ValueError, IndexError):
                pass

        # DOI
        doi = entry.get("prism:doi")

        # URL
        url = None
        for link in entry.get("link", []):
            if link.get("@ref") == "scopus":
                url = link.get("@href")
                break

        # Journal
        journal = entry.get("prism:publicationName")

        # Citations
        citations = None
        cited_by = entry.get("citedby-count")
        if cited_by:
            try:
                citations = int(cited_by)
            except ValueError:
                pass

        # Publication date
        pub_date = None
        if cover_date:
            try:
                pub_date = date.fromisoformat(cover_date)
            except ValueError:
                pass

        # Subject areas as topics
        topics = []
        subject_area = entry.get("subject-area", [])
        if isinstance(subject_area, list):
            for area in subject_area[:5]:
                if isinstance(area, dict):
                    topics.append(area.get("$", ""))

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
            extras={"scopus_id": entry.get("dc:identifier")},
        )
