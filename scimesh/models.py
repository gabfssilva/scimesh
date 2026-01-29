# scimesh/models.py
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class Author:
    """Paper author with optional affiliation and ORCID."""

    name: str
    affiliation: str | None = None
    orcid: str | None = None


@dataclass(frozen=True, slots=True)
class Paper:
    """Normalized paper representation across providers."""

    # Required fields
    title: str
    authors: tuple[Author, ...]
    year: int
    source: str  # Provider name: "arxiv", "scopus", "openalex"

    # Normalized optional fields
    abstract: str | None = None
    doi: str | None = None
    url: str | None = None
    topics: tuple[str, ...] = ()
    citations_count: int | None = None
    publication_date: date | None = None
    journal: str | None = None

    # Open access and PDF fields
    pdf_url: str | None = None
    open_access: bool = False
    references_count: int | None = None

    # Provider-specific fields
    extras: dict[str, Any] = field(default_factory=lambda: {})

    def __hash__(self) -> int:
        """Hash by DOI if available, else by lowercase title + year."""
        if self.doi:
            return hash(self.doi)
        return hash((self.title.lower(), self.year))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Paper):
            return False
        if self.doi and other.doi:
            return self.doi == other.doi
        return self.title.lower() == other.title.lower() and self.year == other.year


@dataclass
class SearchResult:
    """Container for search results from multiple providers."""

    papers: list[Paper]
    total_by_provider: dict[str, int] = field(default_factory=dict)

    def dedupe(self) -> "SearchResult":
        """Remove duplicate papers, merging metadata from different sources."""
        groups: dict[str, list[Paper]] = defaultdict(list)

        for paper in self.papers:
            key = paper.doi if paper.doi else f"{paper.title.lower()}:{paper.year}"
            groups[key].append(paper)

        unique: list[Paper] = []
        for papers in groups.values():
            if len(papers) == 1:
                unique.append(papers[0])
            else:
                unique.append(merge_papers(papers))

        return SearchResult(
            papers=unique,
            total_by_provider=self.total_by_provider,
        )


def merge_papers(papers: list[Paper]) -> Paper:
    """Merge multiple Paper instances (same paper from different sources).

    Prioritizes:
    - Abstract: longest non-null
    - Authors: list with most entries
    - Citation count: highest value
    - References count: highest value
    - Topics: union of all topics
    - Other fields: first non-null value

    Args:
        papers: List of Paper instances to merge. Must not be empty.

    Returns:
        A single merged Paper instance.

    Raises:
        ValueError: If papers list is empty.
    """
    if not papers:
        raise ValueError("Cannot merge empty list of papers")

    if len(papers) == 1:
        return papers[0]

    # Primary source is the first one encountered
    primary = papers[0]

    # Abstract: longest non-null
    abstract = None
    max_abstract_len = 0
    for p in papers:
        if p.abstract and len(p.abstract) > max_abstract_len:
            abstract = p.abstract
            max_abstract_len = len(p.abstract)

    # Authors: list with most entries
    authors = primary.authors
    max_authors = len(authors)
    for p in papers:
        if len(p.authors) > max_authors:
            authors = p.authors
            max_authors = len(p.authors)

    # Citation count: highest value
    citations_count = None
    for p in papers:
        if p.citations_count is not None and (
            citations_count is None or p.citations_count > citations_count
        ):
            citations_count = p.citations_count

    # References count: highest value
    references_count = None
    for p in papers:
        if p.references_count is not None and (
            references_count is None or p.references_count > references_count
        ):
            references_count = p.references_count

    # Topics: union of all topics
    all_topics: set[str] = set()
    for p in papers:
        all_topics.update(p.topics)
    topics = tuple(sorted(all_topics))

    # Other fields: first non-null value
    def first_non_null(*values: Any) -> Any:
        for v in values:
            if v is not None:
                return v
        return None

    doi = first_non_null(*(p.doi for p in papers))
    url = first_non_null(*(p.url for p in papers))
    publication_date = first_non_null(*(p.publication_date for p in papers))
    journal = first_non_null(*(p.journal for p in papers))
    pdf_url = first_non_null(*(p.pdf_url for p in papers))

    # Open access: True if any source says it's open access
    open_access = any(p.open_access for p in papers)

    # Merge extras, prefixing keys with source name if there are conflicts
    merged_extras: dict[str, Any] = {}
    for p in papers:
        for key, value in p.extras.items():
            if key not in merged_extras:
                merged_extras[key] = value
            elif merged_extras[key] != value:
                # Conflict: prefix with source name
                prefixed_key = f"{p.source}_{key}"
                merged_extras[prefixed_key] = value

    return Paper(
        title=primary.title,
        authors=authors,
        year=primary.year,
        source=primary.source,
        abstract=abstract,
        doi=doi,
        url=url,
        topics=topics,
        citations_count=citations_count,
        publication_date=publication_date,
        journal=journal,
        pdf_url=pdf_url,
        open_access=open_access,
        references_count=references_count,
        extras=merged_extras,
    )
