# scimesh/providers/openalex.py
import logging
from collections.abc import AsyncIterator
from datetime import date
from urllib.parse import urlencode

from scimesh.models import Author, Paper
from scimesh.providers.base import Provider
from scimesh.query.combinators import And, Field, Not, Or, Query, YearRange

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
        """
        search_terms: list[str] = []
        filters: list[str] = []
        self._collect_params(query, search_terms, filters)
        return (" ".join(search_terms), ",".join(filters))

    def _collect_params(self, query: Query, search_terms: list[str], filters: list[str]) -> None:
        """Recursively collect search terms and filters from query AST."""
        match query:
            case Field(field="title" | "abstract" | "keyword" | "fulltext", value=v):
                search_terms.append(v)
            case Field(field="author", value=v):
                filters.append(f"raw_author_name.search:{v}")
            case Field(field="doi", value=v):
                filters.append(f"doi:{v}")
            case And(left=l, right=r):
                self._collect_params(l, search_terms, filters)
                self._collect_params(r, search_terms, filters)
            case Or(left=l, right=r):
                self._collect_params(l, search_terms, filters)
                self._collect_params(r, search_terms, filters)
            case Not(operand=o):
                neg_filters: list[str] = []
                neg_search: list[str] = []
                self._collect_params(o, neg_search, neg_filters)
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

    async def search(
        self,
        query: Query,
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Search OpenAlex and yield papers."""
        if self._client is None:
            raise RuntimeError("Provider not initialized. Use 'async with provider:'")

        search_terms, filter_str = self._build_params(query)
        logger.debug("Search terms: %s", search_terms)
        logger.debug("Filters: %s", filter_str)

        params: dict[str, str | int] = {
            "per_page": min(max_results, 200),  # OpenAlex max is 200
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
        logger.debug("Results count: %s", len(data.get("results", [])))
        for work in data.get("results", []):
            paper = self._parse_work(work)
            if paper:
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
