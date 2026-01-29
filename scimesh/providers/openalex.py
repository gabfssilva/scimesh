# scimesh/providers/openalex.py
import logging
from collections.abc import AsyncIterator
from datetime import date
from typing import Literal
from urllib.parse import urlencode

from scimesh.models import Author, Paper
from scimesh.providers.base import Provider
from scimesh.query.combinators import And, CitationRange, Field, Not, Or, Query, YearRange

logger = logging.getLogger(__name__)


class OpenAlex(Provider):
    """OpenAlex paper search provider."""

    name = "openalex"
    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, api_key: str | None = None, mailto: str | None = None):
        super().__init__(api_key)
        self._mailto = mailto

    def _load_from_env(self) -> str | None:
        return None  # OpenAlex doesn't require API key

    def _build_params(self, query: Query) -> tuple[str, str]:
        """Convert Query AST to OpenAlex search and filter params.

        Returns (search_terms, filter_string).

        The search string uses OpenAlex syntax:
        - OR groups: (term1 OR term2)
        - AND between groups: space-separated
        """
        or_groups, filters = self._extract_groups_and_filters(query)
        search_str = self._format_search_groups(or_groups)
        return (search_str, ",".join(filters))

    def _extract_groups_and_filters(self, query: Query) -> tuple[list[list[str]], list[str]]:
        """Extract OR groups and filters from query.

        Returns (or_groups, filters) where or_groups is a list of lists of terms.
        """
        filters: list[str] = []

        # Split query by top-level AND to identify OR groups
        and_groups = self._split_by_and(query)

        or_groups: list[list[str]] = []
        for group in and_groups:
            # Collect search terms from this OR group
            terms = self._collect_or_terms(group)
            if terms:
                or_groups.append(terms)

            # Collect filters from this group
            self._collect_filters(group, filters)

        return (or_groups, filters)

    def _format_search_groups(self, or_groups: list[list[str]]) -> str:
        """Format OR groups into OpenAlex search syntax."""
        search_parts: list[str] = []
        for terms in or_groups:
            if len(terms) == 1:
                search_parts.append(terms[0])
            else:
                search_parts.append(f"({' OR '.join(terms)})")
        return " ".join(search_parts)

    def _count_total_ors(self, or_groups: list[list[str]]) -> int:
        """Count total OR operators needed for the query."""
        return sum(len(terms) - 1 for terms in or_groups if len(terms) > 1)

    def _split_by_and(self, query: Query) -> list[Query]:
        """Split query by top-level AND nodes into groups."""
        match query:
            case And(left=l, right=r):
                return self._split_by_and(l) + self._split_by_and(r)
            case _:
                return [query]

    def _collect_or_terms(self, query: Query) -> list[str]:
        """Collect unique search terms from an OR group, preserving order."""
        seen: set[str] = set()
        terms: list[str] = []
        self._collect_terms_recursive(query, terms, seen)
        return terms

    def _collect_terms_recursive(self, query: Query, terms: list[str], seen: set[str]) -> None:
        """Recursively collect search terms, deduplicating."""
        match query:
            case Field(field="title" | "abstract" | "keyword", value=v):
                if v not in seen:
                    seen.add(v)
                    terms.append(v)
            case Or(left=l, right=r):
                self._collect_terms_recursive(l, terms, seen)
                self._collect_terms_recursive(r, terms, seen)
            case And(left=l, right=r):
                # AND inside an OR group - collect from both sides
                self._collect_terms_recursive(l, terms, seen)
                self._collect_terms_recursive(r, terms, seen)
            case _:
                pass  # Filters, year ranges, etc. handled separately

    def _collect_filters(self, query: Query, filters: list[str]) -> None:
        """Collect filter parameters from query."""
        match query:
            case Field(field="fulltext", value=v):
                filters.append(f"fulltext.search:{v}")
            case Field(field="author", value=v):
                filters.append(f"raw_author_name.search:{v}")
            case Field(field="doi", value=v):
                filters.append(f"doi:{v}")
            case And(left=l, right=r) | Or(left=l, right=r):
                self._collect_filters(l, filters)
                self._collect_filters(r, filters)
            case Not(operand=o):
                neg_filters: list[str] = []
                self._collect_filters(o, neg_filters)
                for f in neg_filters:
                    filters.append(f"!{f}")
            case YearRange(start=s, end=e):
                if s and e:
                    if s == e:
                        filters.append(f"publication_year:{s}")
                    else:
                        filters.append(f"publication_year:{s}-{e}")
                elif s:
                    filters.append(f"publication_year:>{s - 1}")
                elif e:
                    filters.append(f"publication_year:<{e + 1}")
            case CitationRange(min=min_val, max=max_val):
                # OpenAlex uses > and < only, not >= or <=
                if min_val is not None:
                    filters.append(f"cited_by_count:>{min_val - 1}")
                if max_val is not None:
                    filters.append(f"cited_by_count:<{max_val + 1}")
            case _:
                pass  # title, abstract, keyword handled as search terms

    MAX_OR_TERMS = 10  # OpenAlex limit

    async def search(
        self,
        query: Query,
    ) -> AsyncIterator[Paper]:
        """Search OpenAlex and yield papers."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        or_groups, filters = self._extract_groups_and_filters(query)
        filter_str = ",".join(filters)
        total_ors = self._count_total_ors(or_groups)

        logger.debug("OR groups: %s", or_groups)
        logger.debug("Total ORs: %d (max: %d)", total_ors, self.MAX_OR_TERMS)
        logger.debug("Filters: %s", filter_str)

        if total_ors <= self.MAX_OR_TERMS:
            # Single query - under the limit
            search_str = self._format_search_groups(or_groups)
            async for paper in self._execute_search(search_str, filter_str):
                yield paper
        else:
            # Need to split the query into multiple requests
            logger.debug("Splitting query due to OR limit")
            seen_ids: set[str] = set()
            async for paper in self._search_split(or_groups, filter_str, seen_ids):
                yield paper

    async def _execute_search(self, search_terms: str, filter_str: str) -> AsyncIterator[Paper]:
        """Execute search with cursor pagination."""
        if self._client is None:
            raise RuntimeError("Provider not initialized")

        cursor: str | None = "*"  # Initial cursor to start pagination

        while cursor is not None:
            params: dict[str, str | int] = {
                "per_page": 200,  # OpenAlex max is 200
                "cursor": cursor,
            }

            if self._mailto:
                params["mailto"] = self._mailto

            if search_terms:
                params["search"] = search_terms
            if filter_str:
                params["filter"] = filter_str

            url = f"{self.BASE_URL}?{urlencode(params)}"
            logger.debug("Requesting: %s", url)
            response = await self._client.get(url)
            response.raise_for_status()
            logger.debug("Response status: %s", response.status_code)

            data = response.json()
            results = data.get("results", [])
            meta = data.get("meta", {})

            logger.debug(
                "Results count: %s, total: %s, next_cursor: %s",
                len(results),
                meta.get("count"),
                meta.get("next_cursor"),
            )

            for work in results:
                paper = self._parse_work(work)
                if paper:
                    yield paper

            # Get next cursor for pagination
            cursor = meta.get("next_cursor")

    async def _search_split(
        self,
        or_groups: list[list[str]],
        filter_str: str,
        seen_ids: set[str],
    ) -> AsyncIterator[Paper]:
        """Split query into multiple requests when OR limit exceeded.

        Strategy: Split the largest OR group into chunks that fit within limit.
        """
        # Find the largest group (most likely to need splitting)
        if not or_groups:
            return

        largest_idx = max(range(len(or_groups)), key=lambda i: len(or_groups[i]))
        largest_group = or_groups[largest_idx]
        other_groups = [g for i, g in enumerate(or_groups) if i != largest_idx]

        # Calculate how many ORs we have from other groups
        other_ors = self._count_total_ors(other_groups)
        # How many ORs can we use for the largest group per request?
        available_ors = self.MAX_OR_TERMS - other_ors
        # Each OR connects 2 terms, so available_ors ORs = available_ors + 1 terms
        chunk_size = max(1, available_ors + 1)

        logger.debug(
            "Splitting group of %d terms into chunks of %d",
            len(largest_group),
            chunk_size,
        )

        # Split largest group into chunks
        for i in range(0, len(largest_group), chunk_size):
            chunk = largest_group[i : i + chunk_size]
            chunk_groups = other_groups + [chunk]
            search_str = self._format_search_groups(chunk_groups)

            logger.debug("Chunk search: %s", search_str)

            async for paper in self._execute_search(search_str, filter_str):
                # Deduplicate across chunks
                paper_id = paper.extras.get("openalex_id", paper.doi or paper.title)
                if paper_id and paper_id not in seen_ids:
                    seen_ids.add(paper_id)
                    yield paper

    def _parse_work(self, work: dict) -> Paper | None:
        """Parse an OpenAlex work into a Paper."""
        title = work.get("title")
        if not title:
            return None

        # Authors
        authors = []
        for authorship in work.get("authorships", []):
            author_data = authorship.get("author", {})
            name = author_data.get("display_name")
            if name:
                institutions = authorship.get("institutions", [])
                affiliation = institutions[0].get("display_name") if institutions else None
                orcid = author_data.get("orcid")
                if orcid:
                    orcid = orcid.replace("https://orcid.org/", "")
                authors.append(Author(name=name, affiliation=affiliation, orcid=orcid))

        # Year
        year = work.get("publication_year", 0)

        # Abstract (OpenAlex returns inverted index, need to reconstruct)
        abstract = None
        abstract_index = work.get("abstract_inverted_index")
        if abstract_index:
            abstract = self._reconstruct_abstract(abstract_index)

        # DOI
        doi = work.get("doi")
        if doi:
            doi = doi.replace("https://doi.org/", "")

        # URL
        url = work.get("primary_location", {}).get("landing_page_url") or work.get("id")

        # Topics/concepts
        topics = []
        for concept in work.get("concepts", [])[:5]:
            name = concept.get("display_name")
            if name:
                topics.append(name)

        # Citations
        citations = work.get("cited_by_count")

        # Publication date
        pub_date = None
        pub_date_str = work.get("publication_date")
        if pub_date_str:
            try:
                pub_date = date.fromisoformat(pub_date_str)
            except ValueError:
                pass

        # Journal
        journal = None
        source = work.get("primary_location", {}).get("source")
        if source:
            journal = source.get("display_name")

        # Open access info
        open_access_info = work.get("open_access", {})
        is_oa = open_access_info.get("is_oa", False)
        pdf_url = open_access_info.get("oa_url")

        # References count
        references_count = work.get("referenced_works_count")

        return Paper(
            title=title,
            authors=tuple(authors),
            year=year,
            source="openalex",
            abstract=abstract,
            doi=doi,
            url=url,
            topics=tuple(topics),
            citations_count=citations,
            publication_date=pub_date,
            journal=journal,
            pdf_url=pdf_url,
            open_access=is_oa,
            references_count=references_count,
            extras={"openalex_id": work.get("id")},
        )

    def _reconstruct_abstract(self, inverted_index: dict) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        words: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                words.append((pos, word))
        words.sort(key=lambda x: x[0])
        return " ".join(word for _, word in words)

    async def get(self, paper_id: str) -> Paper | None:
        """Fetch a specific paper by DOI or OpenAlex ID.

        Args:
            paper_id: DOI (e.g., "10.1038/nature14539") or OpenAlex ID
                (e.g., "W2741809807")

        Returns:
            Paper if found, None otherwise.
        """
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # Determine if this is a DOI or OpenAlex ID
        if paper_id.startswith("W") or paper_id.startswith("https://openalex.org/"):
            url = f"https://api.openalex.org/works/{paper_id}"
        else:
            # Assume it's a DOI
            doi = paper_id
            if not doi.startswith("https://doi.org/"):
                doi = f"https://doi.org/{doi}"
            url = f"https://api.openalex.org/works/{doi}"

        params: dict[str, str] = {}
        if self._mailto:
            params["mailto"] = self._mailto

        if params:
            url = f"{url}?{urlencode(params)}"

        logger.debug("Fetching: %s", url)
        response = await self._client.get(url)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        work = response.json()
        return self._parse_work(work)

    async def citations(
        self,
        paper_id: str,
        direction: Literal["in", "out", "both"] = "both",
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Get papers citing this paper (in) or cited by this paper (out).

        Args:
            paper_id: DOI or OpenAlex ID.
            direction: "in" for papers citing this one, "out" for papers cited
                by this one, "both" for all.
            max_results: Maximum number of results to return.

        Yields:
            Paper instances.
        """
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        # First, get the OpenAlex ID for this paper
        paper = await self.get(paper_id)
        if paper is None:
            return

        openalex_id = paper.extras.get("openalex_id")
        if not openalex_id:
            return

        # Extract the work ID from the OpenAlex URL
        work_id = openalex_id.split("/")[-1]

        params: dict[str, str | int] = {
            "per_page": min(max_results, 200),
        }
        if self._mailto:
            params["mailto"] = self._mailto

        count = 0

        # Get citing papers (papers that cite this one)
        if direction in ("in", "both"):
            params["filter"] = f"cites:{work_id}"
            url = f"{self.BASE_URL}?{urlencode(params)}"
            logger.debug("Fetching citing papers: %s", url)

            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()

            for work in data.get("results", []):
                if count >= max_results:
                    return
                parsed = self._parse_work(work)
                if parsed:
                    yield parsed
                    count += 1

        # Get referenced papers (papers cited by this one)
        if direction in ("out", "both"):
            params["filter"] = f"cited_by:{work_id}"
            url = f"{self.BASE_URL}?{urlencode(params)}"
            logger.debug("Fetching referenced papers: %s", url)

            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()

            for work in data.get("results", []):
                if count >= max_results:
                    return
                parsed = self._parse_work(work)
                if parsed:
                    yield parsed
                    count += 1
