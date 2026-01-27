# scimesh/models.py
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Author:
    """Paper author with optional affiliation and ORCID."""

    name: str
    affiliation: str | None = None
    orcid: str | None = None


@dataclass(frozen=True)
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

    # Provider-specific fields
    extras: dict[str, Any] = field(default_factory=dict)

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
    errors: dict[str, Exception] = field(default_factory=dict)
    total_by_provider: dict[str, int] = field(default_factory=dict)

    def dedupe(self) -> "SearchResult":
        """Remove duplicate papers, keeping first occurrence."""
        seen: set[str] = set()
        unique: list[Paper] = []

        for paper in self.papers:
            key = paper.doi if paper.doi else f"{paper.title.lower()}:{paper.year}"
            if key not in seen:
                seen.add(key)
                unique.append(paper)

        return SearchResult(
            papers=unique,
            errors=self.errors,
            total_by_provider=self.total_by_provider,
        )
