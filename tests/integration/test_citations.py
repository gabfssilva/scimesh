from __future__ import annotations

import pytest

from scimesh.providers import OpenAlex, Scopus, SemanticScholar
from tests.integration.conftest import (
    ATTENTION_PAPER_DOI,
    ATTENTION_PAPER_YEAR,
    BERT_PAPER_DOI,
    BERT_PAPER_YEAR,
    assert_valid_paper,
    requires_scopus,
)


class TestOpenAlexCitationsIn:
    @pytest.mark.asyncio
    async def test_citations_in_returns_papers(self):
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
                ATTENTION_PAPER_DOI,
                direction="in",
                max_results=10,
            ):
                papers.append(paper)

        assert len(papers) >= 1, "Attention paper is highly cited"

    @pytest.mark.asyncio
    async def test_citations_in_year_constraint(self):
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
                ATTENTION_PAPER_DOI,
                direction="in",
                max_results=20,
            ):
                papers.append(paper)

        for paper in papers:
            assert_valid_paper(paper)
            assert paper.year >= ATTENTION_PAPER_YEAR, (
                f"Citing paper must be from {ATTENTION_PAPER_YEAR} or later, got {paper.year}"
            )

    @pytest.mark.asyncio
    async def test_citations_in_has_valid_papers(self):
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
                ATTENTION_PAPER_DOI,
                direction="in",
                max_results=5,
            ):
                papers.append(paper)

        for paper in papers:
            assert_valid_paper(paper)
            assert paper.title
            assert paper.authors


class TestOpenAlexCitationsOut:
    @pytest.mark.asyncio
    async def test_citations_out_returns_papers(self):
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
                ATTENTION_PAPER_DOI,
                direction="out",
                max_results=10,
            ):
                papers.append(paper)

        assert len(papers) >= 1, "Attention paper has references"

    @pytest.mark.asyncio
    async def test_citations_out_year_constraint(self):
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
                ATTENTION_PAPER_DOI,
                direction="out",
                max_results=20,
            ):
                papers.append(paper)

        for paper in papers:
            assert_valid_paper(paper)
            assert paper.year <= ATTENTION_PAPER_YEAR, (
                f"Reference must be from {ATTENTION_PAPER_YEAR} or earlier, got {paper.year}"
            )


class TestOpenAlexCitationsBoth:
    @pytest.mark.asyncio
    async def test_citations_both_returns_papers(self):
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
                ATTENTION_PAPER_DOI,
                direction="both",
                max_results=20,
            ):
                papers.append(paper)

        assert len(papers) >= 1

        years = [p.year for p in papers]
        has_before = any(y <= ATTENTION_PAPER_YEAR for y in years)
        has_after = any(y >= ATTENTION_PAPER_YEAR for y in years)

        assert has_before or has_after, "Should have papers from before or after"


class TestSemanticScholarCitations:
    @pytest.mark.asyncio
    async def test_citations_in_returns_papers(self):
        ss = SemanticScholar()
        papers = []

        async with ss:
            async for paper in ss.citations(
                ATTENTION_PAPER_DOI,
                direction="in",
                max_results=10,
            ):
                papers.append(paper)

        if len(papers) == 0:
            pytest.skip("SemanticScholar API returned no results (likely rate limited)")
        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_citations_in_year_constraint(self):
        ss = SemanticScholar()
        papers = []

        async with ss:
            async for paper in ss.citations(
                ATTENTION_PAPER_DOI,
                direction="in",
                max_results=10,
            ):
                papers.append(paper)

        if len(papers) == 0:
            pytest.skip("SemanticScholar API returned no results (likely rate limited)")

        for paper in papers:
            assert_valid_paper(paper)
            assert paper.year >= ATTENTION_PAPER_YEAR

    @pytest.mark.asyncio
    async def test_citations_out_returns_papers(self):
        ss = SemanticScholar()
        papers = []

        async with ss:
            async for paper in ss.citations(
                ATTENTION_PAPER_DOI,
                direction="out",
                max_results=10,
            ):
                papers.append(paper)

        if len(papers) == 0:
            pytest.skip("SemanticScholar API returned no results (likely rate limited)")
        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_citations_out_year_constraint(self):
        ss = SemanticScholar()
        papers = []

        async with ss:
            async for paper in ss.citations(
                ATTENTION_PAPER_DOI,
                direction="out",
                max_results=10,
            ):
                papers.append(paper)

        if len(papers) == 0:
            pytest.skip("SemanticScholar API returned no results (likely rate limited)")

        for paper in papers:
            assert_valid_paper(paper)
            assert paper.year <= ATTENTION_PAPER_YEAR


@requires_scopus
@pytest.mark.skip(reason="Requires Citation Overview API permissions")
class TestScopusCitations:
    @pytest.mark.asyncio
    async def test_citations_in_returns_papers(self):
        scopus = Scopus()
        papers = []

        async with scopus:
            async for paper in scopus.citations(
                ATTENTION_PAPER_DOI,
                direction="in",
                max_results=10,
            ):
                papers.append(paper)

        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_citations_in_year_constraint(self):
        scopus = Scopus()
        papers = []

        async with scopus:
            async for paper in scopus.citations(
                ATTENTION_PAPER_DOI,
                direction="in",
                max_results=10,
            ):
                papers.append(paper)

        for paper in papers:
            assert_valid_paper(paper)
            assert paper.year >= ATTENTION_PAPER_YEAR


class TestCitationsForDifferentPapers:
    @pytest.mark.asyncio
    async def test_bert_citations_in(self):
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
                BERT_PAPER_DOI,
                direction="in",
                max_results=10,
            ):
                papers.append(paper)

        assert len(papers) >= 1

        for paper in papers:
            assert_valid_paper(paper)
            assert paper.year >= BERT_PAPER_YEAR

    @pytest.mark.asyncio
    async def test_bert_citations_out(self):
        openalex = OpenAlex()
        papers = []

        async with openalex:
            async for paper in openalex.citations(
                BERT_PAPER_DOI,
                direction="out",
                max_results=10,
            ):
                papers.append(paper)

        assert len(papers) >= 1

        for paper in papers:
            assert_valid_paper(paper)
            assert paper.year <= BERT_PAPER_YEAR
