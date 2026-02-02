from __future__ import annotations

import pytest

from scimesh import search
from scimesh.providers import Scopus
from scimesh.query import author, title, year
from tests.integration.conftest import (
    ATTENTION_PAPER_SCOPUS_ID,
    ATTENTION_PAPER_TITLE,
    ATTENTION_PAPER_YEAR,
    QueryExpectation,
    assert_paper_satisfies,
    requires_scopus,
)


@requires_scopus
class TestScopusSearchByTitle:
    @pytest.mark.asyncio
    async def test_title_filter_returns_matching_papers(self):
        q = title("transformer")
        papers = []

        async for paper in search(q, providers=[Scopus()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(title_contains="transformer", source="scopus"),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_title_filter_multiword(self):
        q = title("neural network")
        papers = []

        async for paper in search(q, providers=[Scopus()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(title_contains="neural", source="scopus"),
            )

        assert len(papers) >= 1


@requires_scopus
class TestScopusSearchByAuthor:
    @pytest.mark.asyncio
    async def test_author_filter_returns_matching_papers(self):
        q = author("Hinton")
        papers = []

        async for paper in search(q, providers=[Scopus()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(author_contains="Hinton", source="scopus"),
            )

        assert len(papers) >= 1


@requires_scopus
class TestScopusSearchByYear:
    @pytest.mark.asyncio
    async def test_year_range_filter(self):
        q = title('"deep learning"') & year(2020, 2022)
        papers = []

        async for paper in search(q, providers=[Scopus()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="deep learning",
                    year_min=2020,
                    year_max=2022,
                    source="scopus",
                ),
            )

        assert len(papers) >= 1


@requires_scopus
class TestScopusSearchCombined:
    @pytest.mark.asyncio
    async def test_title_and_author(self):
        q = title("attention") & author("Vaswani")
        papers = []

        async for paper in search(q, providers=[Scopus()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="attention",
                    author_contains="Vaswani",
                    source="scopus",
                ),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_title_author_and_year(self):
        q = title("attention") & author("Vaswani") & year(2017, 2020)
        papers = []

        async for paper in search(q, providers=[Scopus()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="attention",
                    author_contains="Vaswani",
                    year_min=2017,
                    year_max=2020,
                    source="scopus",
                ),
            )

        assert len(papers) >= 1


@requires_scopus
class TestScopusGetByDoi:
    @pytest.mark.asyncio
    async def test_get_known_paper(self):
        scopus = Scopus()
        async with scopus:
            paper = await scopus.get(ATTENTION_PAPER_SCOPUS_ID)

        assert paper is not None
        assert ATTENTION_PAPER_TITLE.lower() in paper.title.lower()
        assert paper.year == ATTENTION_PAPER_YEAR
        assert paper.source == "scopus"


@requires_scopus
@pytest.mark.skip(reason="Requires Citation Overview API permissions")
class TestScopusCitations:
    @pytest.mark.asyncio
    async def test_citations_in(self):
        scopus = Scopus()
        papers = []

        async with scopus:
            async for paper in scopus.citations(
                ATTENTION_PAPER_SCOPUS_ID,
                direction="in",
                max_results=10,
            ):
                papers.append(paper)

        assert len(papers) >= 1, "Attention paper should have citing papers"
        for paper in papers:
            assert paper.year >= ATTENTION_PAPER_YEAR


@requires_scopus
class TestScopusPaperFields:
    @pytest.mark.asyncio
    async def test_paper_has_required_fields(self):
        q = title("transformer")
        paper = None

        async for p in search(q, providers=[Scopus()], take=1):
            paper = p

        assert paper is not None
        assert paper.title
        assert paper.authors and len(paper.authors) > 0
        assert paper.year
        assert paper.source == "scopus"

    @pytest.mark.asyncio
    async def test_paper_has_doi(self):
        q = title("deep learning")
        papers_with_doi = []

        async for paper in search(q, providers=[Scopus()], take=10):
            if paper.doi:
                papers_with_doi.append(paper)

        assert len(papers_with_doi) > 0, "Scopus papers should have DOI"
