from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

from scimesh.models import Paper

ATTENTION_PAPER_DOI = "10.48550/arXiv.1706.03762"
ATTENTION_PAPER_SCOPUS_ID = "85043317328"
ATTENTION_PAPER_TITLE = "Attention Is All You Need"
ATTENTION_PAPER_YEAR = 2017


BERT_PAPER_DOI = "10.1038/s41586-020-2649-2"
BERT_PAPER_TITLE = "Array programming with NumPy"
BERT_PAPER_YEAR = 2020

requires_scopus = pytest.mark.skipif(
    not os.environ.get("SCOPUS_API_KEY"),
    reason="SCOPUS_API_KEY not set",
)

requires_unpaywall = pytest.mark.skipif(
    not os.environ.get("UNPAYWALL_EMAIL"),
    reason="UNPAYWALL_EMAIL not set",
)


@dataclass(frozen=True)
class QueryExpectation:
    title_contains: str | None = None
    author_contains: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    citations_min: int | None = None
    citations_max: int | None = None
    has_abstract: bool = False
    has_doi: bool = False
    has_url: bool = False
    source: str | None = None


def assert_paper_satisfies(paper: Paper, expect: QueryExpectation) -> None:
    if expect.title_contains:
        assert expect.title_contains.lower() in paper.title.lower(), (
            f"Title should contain '{expect.title_contains}', got: {paper.title}"
        )

    if expect.author_contains:
        author_names = " ".join(a.name for a in paper.authors).lower()
        names = [a.name for a in paper.authors]
        assert expect.author_contains.lower() in author_names, (
            f"Authors should contain '{expect.author_contains}', got: {names}"
        )

    if expect.year_min is not None:
        assert paper.year >= expect.year_min, (
            f"Year should be >= {expect.year_min}, got: {paper.year}"
        )

    if expect.year_max is not None:
        assert paper.year <= expect.year_max, (
            f"Year should be <= {expect.year_max}, got: {paper.year}"
        )

    if expect.citations_min is not None:
        assert paper.citations_count is not None, "Paper should have citations_count"
        assert paper.citations_count >= expect.citations_min, (
            f"Citations should be >= {expect.citations_min}, got: {paper.citations_count}"
        )

    if expect.citations_max is not None:
        assert paper.citations_count is not None, "Paper should have citations_count"
        assert paper.citations_count <= expect.citations_max, (
            f"Citations should be <= {expect.citations_max}, got: {paper.citations_count}"
        )

    if expect.has_abstract:
        assert paper.abstract and len(paper.abstract) > 0, (
            f"Paper should have abstract, got: {paper.abstract!r}"
        )

    if expect.has_doi:
        assert paper.doi, f"Paper should have DOI, got: {paper.doi}"

    if expect.has_url:
        assert paper.url, f"Paper should have URL, got: {paper.url}"

    if expect.source:
        assert paper.source == expect.source, (
            f"Paper source should be '{expect.source}', got: {paper.source}"
        )


def assert_valid_paper(paper: Paper) -> None:
    assert paper.title and len(paper.title) > 0, "Paper must have title"
    assert paper.authors is not None, "Paper must have authors tuple"
    assert paper.year and 1900 <= paper.year <= 2030, f"Invalid year: {paper.year}"
    assert paper.source in ("arxiv", "openalex", "scopus", "semantic_scholar"), (
        f"Unknown source: {paper.source}"
    )


def assert_search_result_valid(result, *, min_papers: int = 1) -> None:
    from scimesh.models import SearchResult

    assert isinstance(result, SearchResult)
    assert result.papers is not None
    assert len(result.papers) >= min_papers, (
        f"Expected at least {min_papers} papers, got {len(result.papers)}"
    )
    assert isinstance(result.total_by_provider, dict)

    for paper in result.papers:
        assert_valid_paper(paper)
