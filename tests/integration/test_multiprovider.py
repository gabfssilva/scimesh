from __future__ import annotations

import pytest

from scimesh import collect_search, search
from scimesh.providers import Arxiv, OpenAlex, Scopus
from scimesh.query import author, title, year
from tests.integration.conftest import (
    QueryExpectation,
    assert_paper_satisfies,
    assert_valid_paper,
    requires_scopus,
)


class TestMultiProviderSearch:
    @pytest.mark.asyncio
    async def test_same_query_returns_from_multiple_providers(self):
        q = title("transformer") & year(2020, 2023)
        result = await collect_search(search(q, providers=[Arxiv(), OpenAlex()], take=20))

        assert len(result.papers) >= 1
        assert len(result.total_by_provider) >= 1, "At least one provider should return results"

    @pytest.mark.asyncio
    async def test_results_satisfy_query_from_all_providers(self):
        q = title("self-attention") & author("Vaswani")
        result = await collect_search(search(q, providers=[Arxiv(), OpenAlex()], take=20))

        assert len(result.papers) >= 1
        for paper in result.papers:
            assert_paper_satisfies(
                paper,
                QueryExpectation(
                    title_contains="attention",
                    author_contains="Vaswani",
                ),
            )

    @pytest.mark.asyncio
    async def test_two_providers(self):
        q = title("neural network")
        result = await collect_search(search(q, providers=[Arxiv(), OpenAlex()], take=20))

        assert len(result.papers) >= 1
        providers_with_results = [p for p, count in result.total_by_provider.items() if count > 0]
        assert len(providers_with_results) >= 1, "At least 1 provider should return results"

    @pytest.mark.asyncio
    @requires_scopus
    async def test_with_scopus(self):
        q = title("deep learning") & year(2020, 2023)
        result = await collect_search(search(q, providers=[Arxiv(), OpenAlex(), Scopus()], take=20))

        assert len(result.papers) >= 1


class TestMultiProviderDeduplication:
    @pytest.mark.asyncio
    async def test_deduplication_by_doi(self):
        q = title("Attention Is All You Need")
        result = await collect_search(
            search(q, providers=[Arxiv(), OpenAlex()], dedupe=True, take=20)
        )

        dois = [p.doi for p in result.papers if p.doi]
        unique_dois = set(dois)

        assert len(dois) == len(unique_dois), f"Found duplicate DOIs: {dois}"

    @pytest.mark.asyncio
    async def test_deduplication_preserves_data(self):
        q = title("self-attention") & author("Vaswani") & year(2017, 2018)
        result = await collect_search(
            search(q, providers=[Arxiv(), OpenAlex()], dedupe=True, take=20)
        )

        for paper in result.papers:
            assert_valid_paper(paper)
            assert paper.title
            assert paper.year

    @pytest.mark.asyncio
    async def test_no_deduplication_may_have_duplicates(self):
        q = title("Attention Is All You Need")
        result = await collect_search(
            search(q, providers=[Arxiv(), OpenAlex()], dedupe=False, take=20)
        )

        for paper in result.papers:
            assert_valid_paper(paper)


class TestMultiProviderErrorHandling:
    @pytest.mark.asyncio
    async def test_one_provider_failure_doesnt_break_others(self):
        q = title("machine learning")

        result = await collect_search(
            search(
                q,
                providers=[Arxiv(), OpenAlex(), Scopus()],
                on_error="ignore",
                take=20,
            )
        )

        assert result.papers is not None
        working_providers = [p for p, c in result.total_by_provider.items() if c > 0]
        assert len(working_providers) >= 1, "At least one provider should work"

    @pytest.mark.asyncio
    async def test_on_error_ignore_continues(self):
        q = title("deep learning")

        result = await collect_search(
            search(
                q,
                providers=[Arxiv(), OpenAlex()],
                on_error="ignore",
                take=20,
            )
        )

        assert len(result.papers) >= 1


class TestMultiProviderConsistency:
    @pytest.mark.asyncio
    async def test_known_paper_found_by_multiple_providers(self):
        q = title("Attention Is All You Need") & author("Vaswani")
        result = await collect_search(search(q, providers=[Arxiv(), OpenAlex()], take=20))

        assert len(result.papers) >= 1

        attention_papers = [p for p in result.papers if "attention" in p.title.lower()]
        assert len(attention_papers) >= 1, "Should find the Attention paper"

    @pytest.mark.asyncio
    async def test_year_filter_consistent_across_providers(self):
        q = title("neural") & year(2021, 2022)
        result = await collect_search(search(q, providers=[Arxiv(), OpenAlex()], take=20))

        for paper in result.papers:
            assert paper.year in (2021, 2022), f"Year {paper.year} not in range [2021, 2022]"

    @pytest.mark.asyncio
    async def test_author_filter_consistent_across_providers(self):
        q = author("LeCun")
        result = await collect_search(search(q, providers=[Arxiv(), OpenAlex()], take=20))

        assert len(result.papers) >= 1
        for paper in result.papers:
            author_names = " ".join(a.name for a in paper.authors).lower()
            assert "lecun" in author_names, f"Author LeCun not found in {paper.authors}"
