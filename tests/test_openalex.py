# tests/test_openalex.py
from unittest.mock import MagicMock

import pytest

from scimesh.providers.openalex import OpenAlex
from scimesh.query.combinators import abstract, author, citations, fulltext, keyword, title, year


def test_translate_title():
    provider = OpenAlex()
    q = title("transformer")
    search, filters = provider._build_params(q)
    # Title searches now use title.search filter for field-specific matching
    assert "title.search:transformer" in filters


def test_translate_author():
    provider = OpenAlex()
    q = author("Vaswani")
    search, filters = provider._build_params(q)
    assert "raw_author_name.search:Vaswani" in filters


def test_translate_abstract():
    provider = OpenAlex()
    q = abstract("attention mechanism")
    search, filters = provider._build_params(q)
    # Abstract searches now use abstract.search filter for field-specific matching
    assert "abstract.search:attention mechanism" in filters


def test_translate_keyword():
    provider = OpenAlex()
    q = keyword("machine learning")
    search, filters = provider._build_params(q)
    assert "machine learning" in search


def test_translate_fulltext():
    provider = OpenAlex()
    q = fulltext("neural network")
    search, filters = provider._build_params(q)
    # OpenAlex has native fulltext search via fulltext.search filter
    assert "fulltext.search:neural network" in filters


def test_translate_and():
    provider = OpenAlex()
    q = title("BERT") & author("Google")
    search, filters = provider._build_params(q)
    # Both title and author use filters
    assert "title.search:BERT" in filters
    assert "raw_author_name.search:Google" in filters


def test_translate_or():
    provider = OpenAlex()
    q = title("BERT") | title("GPT")
    search, filters = provider._build_params(q)
    # OR of same field type uses pipe syntax: filter_name:value1|value2
    assert "title.search:BERT|GPT" in filters


def test_translate_year_range():
    provider = OpenAlex()
    q = year(2020, 2024)
    search, filters = provider._build_params(q)
    assert "publication_year:2020-2024" in filters


def test_translate_year_single():
    provider = OpenAlex()
    q = year(2023, 2023)
    search, filters = provider._build_params(q)
    assert "publication_year:2023" in filters


def test_translate_year_start_only():
    provider = OpenAlex()
    q = year(start=2020)
    search, filters = provider._build_params(q)
    assert "publication_year:>2019" in filters


def test_translate_year_end_only():
    provider = OpenAlex()
    q = year(end=2024)
    search, filters = provider._build_params(q)
    assert "publication_year:<2025" in filters


def test_no_api_key_needed():
    provider = OpenAlex()
    assert provider._api_key is None


def test_reconstruct_abstract():
    provider = OpenAlex()
    inverted_index = {
        "The": [0],
        "quick": [1],
        "brown": [2],
        "fox": [3],
        "jumps": [4],
    }
    result = provider._reconstruct_abstract(inverted_index)
    assert result == "The quick brown fox jumps"


def test_reconstruct_abstract_multiple_occurrences():
    provider = OpenAlex()
    inverted_index = {
        "the": [0, 5],
        "cat": [1],
        "sat": [2],
        "on": [3],
        "mat": [4, 6],
    }
    result = provider._reconstruct_abstract(inverted_index)
    assert result == "the cat sat on mat the mat"


def test_translate_title_abs_no_duplicate_terms():
    """TITLE-ABS should use title_and_abstract.search filter.

    When TITLE-ABS(x) expands to Or(Field(title, x), Field(abstract, x)),
    it should be recognized as the TITLE-ABS pattern and use the dedicated filter.
    """
    from scimesh.query.parser import parse

    provider = OpenAlex()
    q = parse('TITLE-ABS("deep learning") AND TITLE-ABS(imputation)')
    search, filters = provider._build_params(q)

    # Each term should use title_and_abstract.search filter, ANDed via comma
    assert "title_and_abstract.search:deep learning" in filters
    assert "title_and_abstract.search:imputation" in filters


def test_translate_or_inside_title_abs():
    """OR inside TITLE-ABS should use pipe syntax in filters."""
    from scimesh.query.parser import parse

    provider = OpenAlex()
    q = parse('TITLE-ABS("deep learning" OR "neural network")')
    search, filters = provider._build_params(q)

    # OpenAlex OR syntax: filter_name:value1|value2
    assert "title_and_abstract.search:deep learning|neural network" in filters


def test_translate_complex_or_and_structure():
    """Complex query with multiple OR groups connected by AND."""
    from scimesh.query.parser import parse

    provider = OpenAlex()
    q = parse("TITLE-ABS(a OR b) AND TITLE-ABS(c OR d)")
    search, filters = provider._build_params(q)

    # OpenAlex OR syntax: filter_name:value1|value2, ANDed via comma
    assert "title_and_abstract.search:a|b" in filters
    assert "title_and_abstract.search:c|d" in filters


def _make_openalex_response(results: list[dict], total: int, next_cursor: str | None) -> dict:
    """Create a mock OpenAlex API response."""
    return {
        "meta": {
            "count": total,
            "db_response_time_ms": 10,
            "page": None,
            "per_page": 200,
            "next_cursor": next_cursor,
        },
        "results": results,
    }


def _make_work(work_id: str, title: str, year: int) -> dict:
    """Create a minimal OpenAlex work object."""
    return {
        "id": f"https://openalex.org/{work_id}",
        "title": title,
        "publication_year": year,
        "authorships": [],
        "concepts": [],
        "open_access": {"is_oa": False},
    }


@pytest.mark.asyncio
async def test_search_paginates_when_more_results_available():
    """OpenAlex search should paginate when total results exceed per_page limit."""
    provider = OpenAlex()

    # Create 3 pages of results (200 + 200 + 50 = 450 total)
    page1_works = [_make_work(f"W{i}", f"Paper {i}", 2023) for i in range(200)]
    page2_works = [_make_work(f"W{i}", f"Paper {i}", 2023) for i in range(200, 400)]
    page3_works = [_make_work(f"W{i}", f"Paper {i}", 2023) for i in range(400, 450)]

    page1_response = _make_openalex_response(page1_works, 450, "cursor_page2")
    page2_response = _make_openalex_response(page2_works, 450, "cursor_page3")
    page3_response = _make_openalex_response(page3_works, 450, None)

    call_count = 0

    async def mock_get(url: str):
        nonlocal call_count
        call_count += 1
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        if call_count == 1:
            mock_response.json = MagicMock(return_value=page1_response)
        elif call_count == 2:
            mock_response.json = MagicMock(return_value=page2_response)
        else:
            mock_response.json = MagicMock(return_value=page3_response)

        return mock_response

    mock_client = MagicMock()
    mock_client.get = mock_get

    provider._client = mock_client

    from scimesh.query.combinators import title

    papers = []
    async for paper in provider.search(title("test")):
        papers.append(paper)

    # Should have fetched all 450 papers across 3 pages
    assert len(papers) == 450
    assert call_count == 3


@pytest.mark.asyncio
async def test_search_single_page_when_results_fit():
    """OpenAlex search should not paginate when results fit in single page."""
    provider = OpenAlex()

    works = [_make_work(f"W{i}", f"Paper {i}", 2023) for i in range(50)]
    response = _make_openalex_response(works, 50, None)

    call_count = 0

    async def mock_get(url: str):
        nonlocal call_count
        call_count += 1
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=response)
        return mock_response

    mock_client = MagicMock()
    mock_client.get = mock_get

    provider._client = mock_client

    from scimesh.query.combinators import title

    papers = []
    async for paper in provider.search(title("test")):
        papers.append(paper)

    assert len(papers) == 50
    assert call_count == 1


# Tests for CitationRange filter


def test_openalex_citation_filter_min():
    """Test that CitationRange with min translates to filter.

    OpenAlex uses > and < only (not >= or <=), so min=100 becomes >99.
    """
    provider = OpenAlex()
    query = title("transformer") & citations(100)
    search_str, filter_str = provider._build_params(query)
    assert "cited_by_count:>99" in filter_str


def test_openalex_citation_filter_max():
    """Test that CitationRange with max translates to filter.

    OpenAlex uses > and < only (not >= or <=), so max=500 becomes <501.
    """
    provider = OpenAlex()
    query = title("transformer") & citations(max=500)
    search_str, filter_str = provider._build_params(query)
    assert "cited_by_count:<501" in filter_str


def test_openalex_citation_filter_range():
    """Test that CitationRange with min and max translates to filters.

    OpenAlex uses > and < only, so 100-500 becomes >99 and <501.
    """
    provider = OpenAlex()
    query = title("transformer") & citations(100, 500)
    search_str, filter_str = provider._build_params(query)
    assert "cited_by_count:>99" in filter_str
    assert "cited_by_count:<501" in filter_str
