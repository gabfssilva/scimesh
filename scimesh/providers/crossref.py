# scimesh/providers/crossref.py
import logging
import os
from collections.abc import AsyncIterator
from datetime import date
from urllib.parse import urlencode

from scimesh.models import Author, Paper
from scimesh.providers._fulltext_fallback import FulltextFallbackMixin
from scimesh.providers.base import Provider
from scimesh.query.combinators import And, Field, Not, Or, Query, YearRange, has_fulltext

logger = logging.getLogger(__name__)


class CrossRef(FulltextFallbackMixin, Provider):
    """CrossRef paper search provider."""

    name = "crossref"
    BASE_URL = "https://api.crossref.org/works"

    def __init__(
        self,
        api_key: str | None = None,
        mailto: str | None = None,
    ):
        super().__init__(api_key)
        self._mailto = mailto

    def _load_from_env(self) -> str | None:
        return os.getenv("CROSSREF_API_KEY")

    def _build_params(self, query: Query) -> tuple[str, list[str]]:
        """Convert Query AST to CrossRef query and filter params.

        Returns (query_terms, filters).
        """
        query_terms: list[str] = []
        filters: list[str] = []
        self._collect_params(query, query_terms, filters)
        return (" ".join(query_terms), filters)

    def _collect_params(
        self, query: Query, query_terms: list[str], filters: list[str]
    ) -> None:
        """Recursively collect query terms and filters from query AST."""
        match query:
            case Field(field="title", value=v):
                query_terms.append(v)
            case Field(field="abstract", value=v):
                query_terms.append(v)
            case Field(field="keyword", value=v):
                query_terms.append(v)
            case Field(field="fulltext", value=v):
                query_terms.append(v)
            case Field(field="author", value=v):
                filters.append(f"query.author={v}")
            case Field(field="doi", value=v):
                filters.append(f"filter=doi:{v}")
            case And(left=l, right=r):
                self._collect_params(l, query_terms, filters)
                self._collect_params(r, query_terms, filters)
            case Or(left=l, right=r):
                # CrossRef doesn't support OR in filters, collect both
                self._collect_params(l, query_terms, filters)
                self._collect_params(r, query_terms, filters)
            case Not(operand=_):
                # CrossRef doesn't support NOT, skip
                pass
            case YearRange(start=s, end=e):
                if s and e:
                    filters.append(f"filter=from-pub-date:{s},until-pub-date:{e}")
                elif s:
                    filters.append(f"filter=from-pub-date:{s}")
                elif e:
                    filters.append(f"filter=until-pub-date:{e}")

    async def search(
        self,
        query: Query,
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Search CrossRef and yield papers."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # Use local fulltext fallback for fulltext queries
        if has_fulltext(query):
            async for paper in self._search_with_fulltext_filter(query, max_results):
                yield paper
            return

        async for paper in self._search_api(query, max_results):
            yield paper

    async def _search_api(
        self,
        query: Query,
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Execute the actual CrossRef API search."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        query_terms, filters = self._build_params(query)
        logger.debug("Query terms: %s", query_terms)
        logger.debug("Filters: %s", filters)

        params: dict[str, str | int] = {
            "rows": min(max_results, 1000),  # CrossRef max is 1000
        }

        if query_terms:
            params["query"] = query_terms

        # Add mailto for polite pool (higher rate limits)
        if self._mailto:
            params["mailto"] = self._mailto

        # Build filter string from collected filters
        filter_parts: list[str] = []
        other_params: list[str] = []
        for f in filters:
            if f.startswith("filter="):
                filter_parts.append(f.replace("filter=", ""))
            elif f.startswith("query."):
                other_params.append(f)

        if filter_parts:
            params["filter"] = ",".join(filter_parts)

        # Add author query parameter if present
        for p in other_params:
            if p.startswith("query.author="):
                params["query.author"] = p.replace("query.author=", "")

        headers: dict[str, str] = {
            "Accept": "application/json",
        }

        # Add API key to headers if available (Plus tier)
        if self._api_key:
            headers["Crossref-Plus-API-Token"] = f"Bearer {self._api_key}"

        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.debug("Requesting: %s", url)
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        logger.debug("Response status: %s", response.status_code)

        data = response.json()
        items = data.get("message", {}).get("items", [])
        logger.debug("Results count: %s", len(items))

        for item in items:
            paper = self._parse_item(item)
            if paper:
                yield paper

    def _parse_item(self, item: dict) -> Paper | None:
        """Parse a CrossRef item into a Paper."""
        # Title is a list in CrossRef
        titles = item.get("title", [])
        title = titles[0] if titles else None
        if not title:
            return None

        # Authors
        authors = []
        for author_data in item.get("author", []):
            given = author_data.get("given", "")
            family = author_data.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                # Get ORCID (CrossRef includes it as URL)
                orcid = author_data.get("ORCID")
                if orcid:
                    orcid = orcid.replace("http://orcid.org/", "").replace(
                        "https://orcid.org/", ""
                    )

                # Get affiliation
                affiliations = author_data.get("affiliation", [])
                affiliation = affiliations[0].get("name") if affiliations else None

                authors.append(
                    Author(name=name, affiliation=affiliation, orcid=orcid)
                )

        # Year from published-print or published-online
        year = 0
        pub_date = None
        for date_field in ["published-print", "published-online", "created"]:
            date_info = item.get(date_field)
            if date_info and "date-parts" in date_info:
                date_parts = date_info["date-parts"][0]
                if date_parts and len(date_parts) >= 1:
                    year = date_parts[0] or 0
                    if len(date_parts) >= 3:
                        try:
                            pub_date = date(
                                date_parts[0],
                                date_parts[1] or 1,
                                date_parts[2] or 1,
                            )
                        except (ValueError, TypeError):
                            pass
                    elif len(date_parts) >= 2:
                        try:
                            pub_date = date(date_parts[0], date_parts[1] or 1, 1)
                        except (ValueError, TypeError):
                            pass
                    break

        # DOI
        doi = item.get("DOI")

        # URL
        url = item.get("URL")

        # Abstract (CrossRef may include HTML)
        abstract = item.get("abstract")
        if abstract:
            # Basic HTML tag stripping
            import re

            abstract = re.sub(r"<[^>]+>", "", abstract)
            abstract = abstract.strip()

        # Journal from container-title
        container_titles = item.get("container-title", [])
        journal = container_titles[0] if container_titles else None

        # Citations count (is-referenced-by-count)
        citations_count = item.get("is-referenced-by-count")

        # References count
        references_count = item.get("references-count")

        # Subject as topics
        subjects = item.get("subject", [])
        topics = tuple(subjects[:5])

        # Open access (license info)
        is_oa = False
        licenses = item.get("license", [])
        for lic in licenses:
            if lic.get("content-version") == "vor" or "open" in lic.get("URL", "").lower():
                is_oa = True
                break

        # PDF URL from link
        pdf_url = None
        for link in item.get("link", []):
            if link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL")
                break

        return Paper(
            title=title,
            authors=tuple(authors),
            year=year,
            source="crossref",
            abstract=abstract,
            doi=doi,
            url=url,
            topics=topics,
            citations_count=citations_count,
            publication_date=pub_date,
            journal=journal,
            pdf_url=pdf_url,
            open_access=is_oa,
            references_count=references_count,
            extras={"crossref_doi": doi} if doi else {},
        )

    async def get(self, paper_id: str) -> Paper | None:
        """Fetch a specific paper by DOI.

        Args:
            paper_id: DOI (e.g., "10.1038/nature14539").

        Returns:
            Paper if found, None otherwise.
        """
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # CrossRef only supports DOI lookup
        doi = paper_id
        if doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "")

        url = f"{self.BASE_URL}/{doi}"

        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if self._api_key:
            headers["Crossref-Plus-API-Token"] = f"Bearer {self._api_key}"

        params: dict[str, str] = {}
        if self._mailto:
            params["mailto"] = self._mailto

        if params:
            url = f"{url}?{urlencode(params)}"

        logger.debug("Fetching: %s", url)
        response = await self._client.get(url, headers=headers)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()
        item = data.get("message", {})
        return self._parse_item(item)
