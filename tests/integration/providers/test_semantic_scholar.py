from __future__ import annotations

import pytest

from scimesh import search
from scimesh.providers import SemanticScholar
from scimesh.query import author, title, year
from tests.integration.conftest import (
    ATTENTION_PAPER_DOI,
    ATTENTION_PAPER_TITLE,
    ATTENTION_PAPER_YEAR,
    QueryExpectation,
    assert_paper_satisfies,
)


class TestSemanticScholarSearchByTitle:
    @pytest.mark.asyncio
    async def test_title_filter_returns_matching_papers(self):
        q = title("transformer")
        papers = []

        async for paper in search(q, providers=[SemanticScholar()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(title_contains="transformer", source="semantic_scholar"),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_title_filter_multiword(self):
        q = title("neural network")
        papers = []

        async for paper in search(q, providers=[SemanticScholar()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(title_contains="neural", source="semantic_scholar"),
            )

        assert len(papers) >= 1


class TestSemanticScholarSearchByAuthor:
    @pytest.mark.asyncio
    async def test_author_filter_returns_matching_papers(self):
        q = author("Hinton")
        papers = []

        async for paper in search(q, providers=[SemanticScholar()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(author_contains="Hinton", source="semantic_scholar"),
            )

        assert len(papers) >= 1


class TestSemanticScholarSearchByYear:
    @pytest.mark.asyncio
    async def test_year_range_filter(self):
        q = title("deep learning") & year(2020, 2022)
        papers = []

        async for paper in search(q, providers=[SemanticScholar()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="deep learning",
                    year_min=2020,
                    year_max=2022,
                    source="semantic_scholar",
                ),
            )

        assert len(papers) >= 1


class TestSemanticScholarSearchCombined:
    @pytest.mark.asyncio
    async def test_title_and_author(self):
        q = title("attention") & author("Vaswani")
        papers = []

        async for paper in search(q, providers=[SemanticScholar()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="attention",
                    author_contains="Vaswani",
                    source="semantic_scholar",
                ),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_title_author_and_year(self):
        q = title("attention") & author("Vaswani") & year(2017, 2020)
        papers = []

        async for paper in search(q, providers=[SemanticScholar()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="attention",
                    author_contains="Vaswani",
                    year_min=2017,
                    year_max=2020,
                    source="semantic_scholar",
                ),
            )

        assert len(papers) >= 1


class TestSemanticScholarGetByDoi:
    @pytest.mark.asyncio
    async def test_get_known_paper(self):
        ss = SemanticScholar()
        async with ss:
            paper = await ss.get(ATTENTION_PAPER_DOI)

        assert paper is not None
        assert ATTENTION_PAPER_TITLE.lower() in paper.title.lower()
        assert paper.year == ATTENTION_PAPER_YEAR
        assert any("Vaswani" in a.name for a in paper.authors)
        assert paper.source == "semantic_scholar"

    @pytest.mark.asyncio
    async def test_get_returns_citations_count(self):
        ss = SemanticScholar()
        async with ss:
            paper = await ss.get(ATTENTION_PAPER_DOI)

        assert paper is not None
        assert paper.citations_count is not None
        assert paper.citations_count > 10000


class TestSemanticScholarCitations:
    @pytest.mark.asyncio
    async def test_citations_in(self):
        ss = SemanticScholar()
        papers = []

        async with ss:
            async for paper in ss.citations(
                ATTENTION_PAPER_DOI,
                direction="in",
                max_results=10,
            ):
                papers.append(paper)

        assert len(papers) >= 1, "Attention paper should have citing papers"
        for paper in papers:
            assert paper.year >= ATTENTION_PAPER_YEAR, (
                f"Citing paper should be from {ATTENTION_PAPER_YEAR} or later, got {paper.year}"
            )

    @pytest.mark.asyncio
    async def test_citations_out(self):
        ss = SemanticScholar()
        papers = []

        async with ss:
            async for paper in ss.citations(
                ATTENTION_PAPER_DOI,
                direction="out",
                max_results=10,
            ):
                papers.append(paper)

        assert len(papers) >= 1, "Attention paper should have references"
        for paper in papers:
            assert paper.year <= ATTENTION_PAPER_YEAR, (
                f"Reference should be from {ATTENTION_PAPER_YEAR} or earlier, got {paper.year}"
            )


class TestSemanticScholarPaperFields:
    @pytest.mark.asyncio
    async def test_paper_has_required_fields(self):
        q = title("transformer")
        paper = None

        async for p in search(q, providers=[SemanticScholar()], take=1):
            paper = p

        assert paper is not None
        assert paper.title
        assert paper.authors and len(paper.authors) > 0
        assert paper.year
        assert paper.source == "semantic_scholar"

    @pytest.mark.asyncio
    async def test_paper_has_citations_count(self):
        q = title("neural network")
        papers_with_citations = []

        async for paper in search(q, providers=[SemanticScholar()], take=10):
            if paper.citations_count is not None:
                papers_with_citations.append(paper)

        assert len(papers_with_citations) > 0, "Papers should have citations count"

    @pytest.mark.asyncio
    async def test_paper_has_abstract(self):
        q = title("deep learning")
        papers_with_abstract = []

        async for paper in search(q, providers=[SemanticScholar()], take=10):
            if paper.abstract:
                papers_with_abstract.append(paper)

        assert len(papers_with_abstract) > 0, "At least some papers should have abstracts"
