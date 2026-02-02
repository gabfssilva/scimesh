from __future__ import annotations

import pytest

from scimesh import search
from scimesh.providers import OpenAlex
from scimesh.query import author, title, year
from scimesh.query.combinators import citations
from tests.integration.conftest import (
    ATTENTION_PAPER_DOI,
    ATTENTION_PAPER_TITLE,
    ATTENTION_PAPER_YEAR,
    QueryExpectation,
    assert_paper_satisfies,
)


class TestOpenAlexSearchByTitle:
    @pytest.mark.asyncio
    async def test_title_filter_returns_matching_papers(self):
        q = title("transformer")
        papers = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(title_contains="transformer", source="openalex"),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_title_filter_multiword(self):
        q = title("neural network")
        papers = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(title_contains="neural", source="openalex"),
            )

        assert len(papers) >= 1


class TestOpenAlexSearchByAuthor:
    @pytest.mark.asyncio
    async def test_author_filter_returns_matching_papers(self):
        q = author("Hinton")
        papers = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(author_contains="Hinton", source="openalex"),
            )

        assert len(papers) >= 1


class TestOpenAlexSearchByYear:
    @pytest.mark.asyncio
    async def test_year_range_filter(self):
        q = title("deep learning") & year(2020, 2022)
        papers = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="deep learning",
                    year_min=2020,
                    year_max=2022,
                    source="openalex",
                ),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_year_min_only(self):
        q = title("machine learning") & year(2022, None)
        papers = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(year_min=2022, source="openalex"),
            )

        assert len(papers) >= 1


class TestOpenAlexSearchByCitations:
    @pytest.mark.asyncio
    async def test_citations_min_filter(self):
        q = title("deep learning") & citations(min=1000)
        papers = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    citations_min=1000,
                    source="openalex",
                ),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_citations_range_filter(self):
        q = title("neural network") & citations(min=100, max=500)
        papers = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    citations_min=100,
                    citations_max=500,
                    source="openalex",
                ),
            )

        assert len(papers) >= 1


class TestOpenAlexSearchCombined:
    @pytest.mark.asyncio
    async def test_title_and_author(self):
        q = title("attention") & author("Vaswani")
        papers = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="attention",
                    author_contains="Vaswani",
                    source="openalex",
                ),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_title_author_year_citations(self):
        q = title("learning") & year(2015, 2020) & citations(min=500)
        papers = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="learning",
                    year_min=2015,
                    year_max=2020,
                    citations_min=500,
                    source="openalex",
                ),
            )

        assert len(papers) >= 1


class TestOpenAlexGetByDoi:
    @pytest.mark.asyncio
    async def test_get_known_paper(self):
        openalex = OpenAlex()
        async with openalex:
            paper = await openalex.get(ATTENTION_PAPER_DOI)

        assert paper is not None
        assert ATTENTION_PAPER_TITLE.lower() in paper.title.lower()
        assert any("Vaswani" in a.name for a in paper.authors)
        assert paper.source == "openalex"

    @pytest.mark.asyncio
    async def test_get_returns_citations_count(self):
        openalex = OpenAlex()
        async with openalex:
            paper = await openalex.get(ATTENTION_PAPER_DOI)

        assert paper is not None
        assert paper.citations_count is not None
        assert paper.citations_count > 0


class TestOpenAlexCitations:
    @pytest.mark.asyncio
    async def test_citations_in(self):
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
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
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
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


class TestOpenAlexPagination:
    @pytest.mark.asyncio
    async def test_fetches_multiple_pages(self):
        q = title("machine learning")
        papers = []
        openalex = OpenAlex()

        async with openalex:
            count = 0
            async for paper in openalex.search(q):
                papers.append(paper)
                count += 1
                if count >= 250:
                    break

        assert len(papers) >= 200, "Should fetch more than one page"


class TestOpenAlexPaperFields:
    @pytest.mark.asyncio
    async def test_paper_has_required_fields(self):
        q = title("transformer")
        paper = None

        async for p in search(q, providers=[OpenAlex()], take=1):
            paper = p

        assert paper is not None
        assert paper.title
        assert paper.authors and len(paper.authors) > 0
        assert paper.year
        assert paper.source == "openalex"

    @pytest.mark.asyncio
    async def test_paper_has_doi(self):
        q = title("deep learning")
        papers_with_doi = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            if paper.doi:
                papers_with_doi.append(paper)

        assert len(papers_with_doi) > 0, "At least some papers should have DOI"

    @pytest.mark.asyncio
    async def test_paper_has_citations_count(self):
        q = title("neural network")
        papers_with_citations = []

        async for paper in search(q, providers=[OpenAlex()], take=10):
            if paper.citations_count is not None:
                papers_with_citations.append(paper)

        assert len(papers_with_citations) > 0, "Papers should have citations count"
