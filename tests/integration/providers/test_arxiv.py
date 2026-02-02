from __future__ import annotations

import pytest

from scimesh import search
from scimesh.providers import Arxiv
from scimesh.query import author, title, year
from tests.integration.conftest import (
    ATTENTION_PAPER_DOI,
    ATTENTION_PAPER_TITLE,
    ATTENTION_PAPER_YEAR,
    QueryExpectation,
    assert_paper_satisfies,
)


class TestArxivSearchByTitle:
    @pytest.mark.asyncio
    async def test_title_filter_returns_matching_papers(self):
        q = title("transformer")

        count = 0

        async for paper in search(q, providers=[Arxiv()], take=10):
            count += 1
            assert_paper_satisfies(
                paper,
                QueryExpectation(title_contains="transformer", source="arxiv"),
            )

        assert count == 10

    @pytest.mark.asyncio
    async def test_title_filter_multiword(self):
        q = title("neural network")
        papers = []

        async for paper in search(q, providers=[Arxiv()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(title_contains="neural", source="arxiv"),
            )

        assert len(papers) >= 1


class TestArxivSearchByAuthor:
    @pytest.mark.asyncio
    async def test_author_filter_returns_matching_papers(self):
        q = author("Hinton")
        papers = []

        async for paper in search(q, providers=[Arxiv()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(author_contains="Hinton", source="arxiv"),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_author_filter_full_name(self):
        q = author("Geoffrey Hinton")
        papers = []

        async for paper in search(q, providers=[Arxiv()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(author_contains="Hinton", source="arxiv"),
            )

        assert len(papers) >= 1


class TestArxivSearchByYear:
    @pytest.mark.asyncio
    async def test_year_range_filter(self):
        q = title("deep learning") & year(2020, 2022)
        papers = []

        async for paper in search(q, providers=[Arxiv()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="deep learning",
                    year_min=2020,
                    year_max=2022,
                    source="arxiv",
                ),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_year_min_only(self):
        q = title("machine learning") & year(2021, None)
        papers = []

        async for paper in search(q, providers=[Arxiv()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(year_min=2021, source="arxiv"),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_year_max_only(self):
        q = title("neural") & year(None, 2015)
        papers = []

        async for paper in search(q, providers=[Arxiv()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(year_max=2015, source="arxiv"),
            )

        assert len(papers) >= 1


class TestArxivSearchCombined:
    @pytest.mark.asyncio
    async def test_title_and_author(self):
        q = title("self-attention") & author("Vaswani")
        papers = []

        async for paper in search(q, providers=[Arxiv()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="attention",
                    author_contains="Vaswani",
                    source="arxiv",
                ),
            )

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_title_author_and_year(self):
        q = title("self-attention") & author("Vaswani") & year(2017, 2020)
        papers = []

        async for paper in search(q, providers=[Arxiv()], take=10):
            papers.append(paper)
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="attention",
                    author_contains="Vaswani",
                    year_min=2017,
                    year_max=2020,
                    source="arxiv",
                ),
            )

        assert len(papers) >= 1


class TestArxivGetByDoi:
    @pytest.mark.asyncio
    async def test_get_known_paper(self):
        arxiv = Arxiv()
        async with arxiv:
            paper = await arxiv.get(ATTENTION_PAPER_DOI)

        assert paper is not None
        assert ATTENTION_PAPER_TITLE.lower() in paper.title.lower()
        assert paper.year == ATTENTION_PAPER_YEAR
        assert any("Vaswani" in a.name for a in paper.authors)
        assert paper.source == "arxiv"

    @pytest.mark.asyncio
    async def test_get_returns_abstract(self):
        arxiv = Arxiv()
        async with arxiv:
            paper = await arxiv.get(ATTENTION_PAPER_DOI)

        assert paper.abstract is not None
        assert len(paper.abstract) > 100


class TestArxivPagination:
    @pytest.mark.asyncio
    async def test_fetches_multiple_pages(self):
        q = title("neural network")
        papers = []
        arxiv = Arxiv()

        async with arxiv:
            count = 0
            async for paper in arxiv.search(q):
                papers.append(paper)
                count += 1
                if count >= 150:
                    break

        assert len(papers) >= 100, "Should fetch more than one page (page_size=100)"


class TestArxivPaperFields:
    @pytest.mark.asyncio
    async def test_paper_has_required_fields(self):
        q = title("transformer")
        paper = None

        async for p in search(q, providers=[Arxiv()], take=1):
            paper = p

        assert paper is not None
        assert paper.title
        assert paper.authors and len(paper.authors) > 0
        assert paper.year
        assert paper.source == "arxiv"
        assert paper.url and paper.url.startswith("http")

    @pytest.mark.asyncio
    async def test_paper_has_abstract(self):
        q = title("deep learning")
        papers_with_abstract = []

        async for paper in search(q, providers=[Arxiv()], take=10):
            if paper.abstract:
                papers_with_abstract.append(paper)

        assert len(papers_with_abstract) > 0, "At least some papers should have abstracts"
