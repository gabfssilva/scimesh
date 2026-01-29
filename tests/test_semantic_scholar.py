# tests/test_semantic_scholar.py
import os
import re
from unittest.mock import MagicMock

import pytest

from scimesh.providers.semantic_scholar import SemanticScholar
from scimesh.query.combinators import abstract, author, doi, fulltext, keyword, title, year


def test_translate_title():
    provider = SemanticScholar()
    q = title("transformer")
    query_str, year_start, year_end = provider._translate_query(q)
    assert '"transformer"' in query_str
    assert year_start is None
    assert year_end is None


def test_translate_author():
    provider = SemanticScholar()
    q = author("Vaswani")
    query_str, year_start, year_end = provider._translate_query(q)
    assert "Vaswani" in query_str


def test_translate_abstract():
    provider = SemanticScholar()
    q = abstract("attention mechanism")
    query_str, year_start, year_end = provider._translate_query(q)
    assert "attention mechanism" in query_str


def test_translate_keyword():
    provider = SemanticScholar()
    q = keyword("machine learning")
    query_str, year_start, year_end = provider._translate_query(q)
    assert "machine learning" in query_str


def test_translate_fulltext():
    provider = SemanticScholar()
    q = fulltext("neural network")
    query_str, year_start, year_end = provider._translate_query(q)
    assert "neural network" in query_str


def test_translate_doi():
    provider = SemanticScholar()
    q = doi("10.1234/example")
    query_str, year_start, year_end = provider._translate_query(q)
    assert "10.1234/example" in query_str


def test_translate_and():
    provider = SemanticScholar()
    q = title("BERT") & author("Google")
    query_str, year_start, year_end = provider._translate_query(q)
    assert '"BERT"' in query_str
    assert "Google" in query_str


def test_translate_or():
    provider = SemanticScholar()
    q = title("BERT") | title("GPT")
    query_str, year_start, year_end = provider._translate_query(q)
    assert "BERT" in query_str
    assert "GPT" in query_str
    assert "|" in query_str


def test_translate_not():
    provider = SemanticScholar()
    q = ~title("survey")
    query_str, year_start, year_end = provider._translate_query(q)
    assert "-" in query_str
    assert "survey" in query_str


def test_translate_year_range():
    provider = SemanticScholar()
    q = year(2020, 2024)
    query_str, year_start, year_end = provider._translate_query(q)
    assert year_start == 2020
    assert year_end == 2024


def test_translate_year_single():
    provider = SemanticScholar()
    q = year(2023, 2023)
    query_str, year_start, year_end = provider._translate_query(q)
    assert year_start == 2023
    assert year_end == 2023


def test_translate_year_start_only():
    provider = SemanticScholar()
    q = year(start=2020)
    query_str, year_start, year_end = provider._translate_query(q)
    assert year_start == 2020
    assert year_end is None


def test_translate_year_end_only():
    provider = SemanticScholar()
    q = year(end=2024)
    query_str, year_start, year_end = provider._translate_query(q)
    assert year_start is None
    assert year_end == 2024


def test_translate_complex_query():
    provider = SemanticScholar()
    q = (title("deep learning") & author("LeCun")) | keyword("CNN")
    query_str, year_start, year_end = provider._translate_query(q)
    assert "deep learning" in query_str
    assert "LeCun" in query_str
    assert "CNN" in query_str


def test_translate_query_with_year():
    provider = SemanticScholar()
    q = title("transformer") & year(2020, 2024)
    query_str, year_start, year_end = provider._translate_query(q)
    assert '"transformer"' in query_str
    assert year_start == 2020
    assert year_end == 2024


def test_loads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "test-key-123")
    provider = SemanticScholar()
    assert provider._api_key == "test-key-123"


def test_explicit_api_key_overrides_env(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "env-key")
    provider = SemanticScholar(api_key="explicit-key")
    assert provider._api_key == "explicit-key"


def test_no_api_key_returns_none():
    # Clear any existing env var
    original = os.environ.pop("SEMANTIC_SCHOLAR_API_KEY", None)
    try:
        provider = SemanticScholar()
        assert provider._api_key is None
    finally:
        if original:
            os.environ["SEMANTIC_SCHOLAR_API_KEY"] = original


def test_provider_name():
    provider = SemanticScholar()
    assert provider.name == "semantic_scholar"


def test_base_url():
    provider = SemanticScholar()
    assert provider.BASE_URL == "https://api.semanticscholar.org/graph/v1/paper/search"


def test_parse_paper_minimal():
    provider = SemanticScholar()
    paper_data = {
        "paperId": "abc123",
        "title": "Test Paper",
        "authors": [{"name": "John Doe"}],
        "year": 2023,
    }
    paper = provider._parse_paper(paper_data)
    assert paper is not None
    assert paper.title == "Test Paper"
    assert len(paper.authors) == 1
    assert paper.authors[0].name == "John Doe"
    assert paper.year == 2023
    assert paper.source == "semantic_scholar"
    assert paper.extras.get("semanticScholarId") == "abc123"
    assert paper.url == "https://www.semanticscholar.org/paper/abc123"


def test_parse_paper_full():
    provider = SemanticScholar()
    paper_data = {
        "paperId": "abc123",
        "title": "Attention Is All You Need",
        "authors": [
            {"name": "Ashish Vaswani"},
            {"name": "Noam Shazeer"},
        ],
        "year": 2017,
        "abstract": "The dominant sequence transduction models...",
        "citationCount": 50000,
        "referenceCount": 35,
        "venue": "NeurIPS",
        "publicationDate": "2017-06-12",
        "isOpenAccess": True,
        "openAccessPdf": {"url": "https://arxiv.org/pdf/1706.03762.pdf"},
        "fieldsOfStudy": ["Computer Science", "Machine Learning"],
        "externalIds": {"DOI": "10.48550/arXiv.1706.03762"},
    }
    paper = provider._parse_paper(paper_data)
    assert paper is not None
    assert paper.title == "Attention Is All You Need"
    assert len(paper.authors) == 2
    assert paper.authors[0].name == "Ashish Vaswani"
    assert paper.year == 2017
    assert paper.abstract == "The dominant sequence transduction models..."
    assert paper.doi == "10.48550/arXiv.1706.03762"
    assert paper.citations_count == 50000
    assert paper.references_count == 35
    assert paper.journal == "NeurIPS"
    assert paper.publication_date is not None
    assert paper.publication_date.isoformat() == "2017-06-12"
    assert paper.open_access is True
    assert paper.pdf_url == "https://arxiv.org/pdf/1706.03762.pdf"
    assert paper.topics == ("Computer Science", "Machine Learning")


def test_parse_paper_no_title():
    provider = SemanticScholar()
    paper_data = {
        "paperId": "abc123",
        "authors": [{"name": "John Doe"}],
        "year": 2023,
    }
    paper = provider._parse_paper(paper_data)
    assert paper is None


def test_parse_paper_empty_venue():
    provider = SemanticScholar()
    paper_data = {
        "paperId": "abc123",
        "title": "Test Paper",
        "authors": [],
        "year": 2023,
        "venue": "",
    }
    paper = provider._parse_paper(paper_data)
    assert paper is not None
    assert paper.journal is None


def test_parse_paper_null_external_ids():
    provider = SemanticScholar()
    paper_data = {
        "paperId": "abc123",
        "title": "Test Paper",
        "authors": [],
        "year": 2023,
        "externalIds": None,
    }
    paper = provider._parse_paper(paper_data)
    assert paper is not None
    assert paper.doi is None


def test_parse_paper_null_fields_of_study():
    provider = SemanticScholar()
    paper_data = {
        "paperId": "abc123",
        "title": "Test Paper",
        "authors": [],
        "year": 2023,
        "fieldsOfStudy": None,
    }
    paper = provider._parse_paper(paper_data)
    assert paper is not None
    assert paper.topics == ()


def test_parse_paper_invalid_date():
    provider = SemanticScholar()
    paper_data = {
        "paperId": "abc123",
        "title": "Test Paper",
        "authors": [],
        "year": 2023,
        "publicationDate": "invalid-date",
    }
    paper = provider._parse_paper(paper_data)
    assert paper is not None
    assert paper.publication_date is None


def test_page_size_constant():
    """Test that PAGE_SIZE constant is 100 (Semantic Scholar max per request)."""
    assert SemanticScholar.PAGE_SIZE == 100


def test_max_total_results_constant():
    """Test that MAX_TOTAL_RESULTS constant is 1000 (Semantic Scholar relevance search limit)."""
    assert SemanticScholar.MAX_TOTAL_RESULTS == 1000


def _make_semantic_scholar_response(results: list[dict], total: int, offset: int) -> dict:
    """Create a mock Semantic Scholar API response."""
    return {
        "total": total,
        "offset": offset,
        "data": results,
    }


def _make_paper(paper_id: str, title: str, year: int) -> dict:
    """Create a minimal Semantic Scholar paper object."""
    return {
        "paperId": paper_id,
        "title": title,
        "year": year,
        "authors": [],
    }


@pytest.mark.asyncio
async def test_search_paginates_with_offset():
    """Semantic Scholar search should paginate using offset parameter."""
    provider = SemanticScholar()

    # Create 3 pages of results (100 + 100 + 50 = 250 total)
    page1_papers = [_make_paper(f"paper{i}", f"Paper {i}", 2023) for i in range(100)]
    page2_papers = [_make_paper(f"paper{i}", f"Paper {i}", 2023) for i in range(100, 200)]
    page3_papers = [_make_paper(f"paper{i}", f"Paper {i}", 2023) for i in range(200, 250)]

    page1_response = _make_semantic_scholar_response(page1_papers, 250, 0)
    page2_response = _make_semantic_scholar_response(page2_papers, 250, 100)
    page3_response = _make_semantic_scholar_response(page3_papers, 250, 200)

    call_count = 0
    captured_urls: list[str] = []

    async def mock_get(url: str, headers: dict | None = None):
        nonlocal call_count
        call_count += 1
        captured_urls.append(url)

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

    papers = []
    async for paper in provider.search(title("test")):
        papers.append(paper)

    # Should have fetched all 250 papers across 3 pages
    assert len(papers) == 250
    assert call_count == 3

    # Verify offset parameter is in URLs
    # First call may not have offset or has offset=0
    assert "offset=0" in captured_urls[0] or "offset" not in captured_urls[0]
    assert "offset=100" in captured_urls[1]
    assert "offset=200" in captured_urls[2]


@pytest.mark.asyncio
async def test_search_single_page_when_results_fit():
    """Semantic Scholar search should not paginate when results fit in single page."""
    provider = SemanticScholar()

    papers_data = [_make_paper(f"paper{i}", f"Paper {i}", 2023) for i in range(50)]
    response = _make_semantic_scholar_response(papers_data, 50, 0)

    call_count = 0

    async def mock_get(url: str, headers: dict | None = None):
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

    papers = []
    async for paper in provider.search(title("test")):
        papers.append(paper)

    assert len(papers) == 50
    assert call_count == 1


@pytest.mark.asyncio
async def test_search_stops_at_max_total_results():
    """Semantic Scholar search should stop at MAX_TOTAL_RESULTS (1000)."""
    provider = SemanticScholar()

    # Simulate a query that has 1500 total results, but we should stop at 1000
    page_count = 0

    async def mock_get(url: str, headers: dict | None = None):
        nonlocal page_count
        page_count += 1

        # Parse offset from URL to determine which page we're on
        offset_match = re.search(r"offset=(\d+)", url)
        offset = int(offset_match.group(1)) if offset_match else 0

        # Generate 100 papers per page
        papers = [
            _make_paper(f"paper{offset + i}", f"Paper {offset + i}", 2023) for i in range(100)
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value=_make_semantic_scholar_response(papers, 1500, offset)
        )
        return mock_response

    mock_client = MagicMock()
    mock_client.get = mock_get

    provider._client = mock_client

    papers = []
    async for paper in provider.search(title("test")):
        papers.append(paper)

    # Should stop at 1000 results (MAX_TOTAL_RESULTS), which is 10 pages
    assert len(papers) == 1000
    assert page_count == 10
