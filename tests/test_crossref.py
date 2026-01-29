# tests/test_crossref.py
import os

import pytest

from scimesh.providers.crossref import CrossRef
from scimesh.query.combinators import abstract, author, doi, fulltext, keyword, title, year


def test_translate_title():
    provider = CrossRef()
    q = title("transformer")
    query_terms, filters = provider._build_params(q)
    assert "transformer" in query_terms


def test_translate_author():
    provider = CrossRef()
    q = author("Vaswani")
    query_terms, filters = provider._build_params(q)
    assert "query.author=Vaswani" in filters


def test_translate_abstract():
    provider = CrossRef()
    q = abstract("attention mechanism")
    query_terms, filters = provider._build_params(q)
    assert "attention mechanism" in query_terms


def test_translate_keyword():
    provider = CrossRef()
    q = keyword("machine learning")
    query_terms, filters = provider._build_params(q)
    assert "machine learning" in query_terms


def test_translate_fulltext():
    provider = CrossRef()
    q = fulltext("neural network")
    query_terms, filters = provider._build_params(q)
    assert "neural network" in query_terms


def test_translate_doi():
    provider = CrossRef()
    q = doi("10.1234/example")
    query_terms, filters = provider._build_params(q)
    assert "filter=doi:10.1234/example" in filters


def test_translate_and():
    provider = CrossRef()
    q = title("BERT") & author("Google")
    query_terms, filters = provider._build_params(q)
    assert "BERT" in query_terms
    assert "query.author=Google" in filters


def test_translate_or():
    provider = CrossRef()
    q = title("BERT") | title("GPT")
    query_terms, filters = provider._build_params(q)
    assert "BERT" in query_terms
    assert "GPT" in query_terms


def test_translate_not():
    # CrossRef doesn't support NOT, so it should be ignored
    provider = CrossRef()
    q = ~title("survey")
    query_terms, filters = provider._build_params(q)
    assert "survey" not in query_terms
    assert len(filters) == 0


def test_translate_year_range():
    provider = CrossRef()
    q = year(2020, 2024)
    query_terms, filters = provider._build_params(q)
    assert "filter=from-pub-date:2020,until-pub-date:2024" in filters


def test_translate_year_start_only():
    provider = CrossRef()
    q = year(start=2020)
    query_terms, filters = provider._build_params(q)
    assert "filter=from-pub-date:2020" in filters


def test_translate_year_end_only():
    provider = CrossRef()
    q = year(end=2024)
    query_terms, filters = provider._build_params(q)
    assert "filter=until-pub-date:2024" in filters


def test_translate_complex_query():
    provider = CrossRef()
    q = (title("deep learning") & author("LeCun")) | keyword("CNN")
    query_terms, filters = provider._build_params(q)
    assert "deep learning" in query_terms
    assert "CNN" in query_terms
    assert "query.author=LeCun" in filters


def test_loads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("CROSSREF_API_KEY", "test-key-123")
    provider = CrossRef()
    assert provider._api_key == "test-key-123"


def test_explicit_api_key_overrides_env(monkeypatch):
    monkeypatch.setenv("CROSSREF_API_KEY", "env-key")
    provider = CrossRef(api_key="explicit-key")
    assert provider._api_key == "explicit-key"


def test_no_api_key_returns_none():
    original = os.environ.pop("CROSSREF_API_KEY", None)
    try:
        provider = CrossRef()
        assert provider._api_key is None
    finally:
        if original:
            os.environ["CROSSREF_API_KEY"] = original


def test_mailto_parameter():
    provider = CrossRef(mailto="test@example.com")
    assert provider._mailto == "test@example.com"


def test_provider_name():
    provider = CrossRef()
    assert provider.name == "crossref"


def test_base_url():
    provider = CrossRef()
    assert provider.BASE_URL == "https://api.crossref.org/works"


def test_parse_item_basic():
    provider = CrossRef()
    item = {
        "title": ["Test Paper Title"],
        "author": [
            {
                "given": "John",
                "family": "Doe",
                "ORCID": "https://orcid.org/0000-0001-2345-6789",
                "affiliation": [{"name": "Test University"}],
            }
        ],
        "DOI": "10.1234/test",
        "URL": "https://doi.org/10.1234/test",
        "published-print": {"date-parts": [[2023, 6, 15]]},
        "container-title": ["Test Journal"],
        "is-referenced-by-count": 42,
        "references-count": 25,
        "abstract": "<p>This is the abstract.</p>",
        "subject": ["Computer Science", "Machine Learning"],
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.title == "Test Paper Title"
    assert len(paper.authors) == 1
    assert paper.authors[0].name == "John Doe"
    assert paper.authors[0].orcid == "0000-0001-2345-6789"
    assert paper.authors[0].affiliation == "Test University"
    assert paper.doi == "10.1234/test"
    assert paper.url == "https://doi.org/10.1234/test"
    assert paper.year == 2023
    assert paper.publication_date is not None
    assert paper.publication_date.year == 2023
    assert paper.publication_date.month == 6
    assert paper.publication_date.day == 15
    assert paper.journal == "Test Journal"
    assert paper.citations_count == 42
    assert paper.references_count == 25
    assert paper.abstract == "This is the abstract."
    assert "Computer Science" in paper.topics
    assert paper.source == "crossref"
    assert paper.extras.get("crossref_doi") == "10.1234/test"


def test_parse_item_no_title():
    provider = CrossRef()
    item = {"author": [{"given": "John", "family": "Doe"}]}

    paper = provider._parse_item(item)
    assert paper is None


def test_parse_item_minimal():
    provider = CrossRef()
    item = {"title": ["Minimal Paper"]}

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.title == "Minimal Paper"
    assert paper.authors == ()
    assert paper.year == 0
    assert paper.doi is None


def test_parse_item_published_online_fallback():
    provider = CrossRef()
    item = {
        "title": ["Online Paper"],
        "published-online": {"date-parts": [[2024, 1, 1]]},
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.year == 2024


def test_parse_item_orcid_http_prefix():
    provider = CrossRef()
    item = {
        "title": ["ORCID Test"],
        "author": [
            {
                "given": "Jane",
                "family": "Smith",
                "ORCID": "http://orcid.org/0000-0002-1234-5678",
            }
        ],
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.authors[0].orcid == "0000-0002-1234-5678"


def test_parse_item_pdf_link():
    provider = CrossRef()
    item = {
        "title": ["PDF Paper"],
        "link": [
            {"content-type": "text/html", "URL": "https://example.com/paper"},
            {"content-type": "application/pdf", "URL": "https://example.com/paper.pdf"},
        ],
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.pdf_url == "https://example.com/paper.pdf"


def test_parse_item_open_access():
    provider = CrossRef()
    item = {
        "title": ["Open Access Paper"],
        "license": [
            {"content-version": "vor", "URL": "https://creativecommons.org/licenses/by/4.0/"}
        ],
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.open_access is True


def test_page_size_constant():
    """CrossRef provider should have PAGE_SIZE = 1000."""
    provider = CrossRef()
    assert provider.PAGE_SIZE == 1000


def _make_crossref_response(items: list[dict], total: int, next_cursor: str | None) -> dict:
    """Create a mock CrossRef API response."""
    response = {
        "status": "ok",
        "message": {
            "total-results": total,
            "items": items,
        },
    }
    if next_cursor:
        response["message"]["next-cursor"] = next_cursor
    return response


def _make_crossref_item(doi: str, title_text: str, year: int) -> dict:
    """Create a minimal CrossRef work object."""
    return {
        "DOI": doi,
        "title": [title_text],
        "published-print": {"date-parts": [[year]]},
        "author": [],
    }


@pytest.mark.asyncio
async def test_search_paginates_with_cursor():
    """CrossRef search should paginate using cursor-based deep paging."""
    from unittest.mock import MagicMock

    provider = CrossRef()

    # Create 3 pages of results (1000 + 1000 + 500 = 2500 total)
    page1_items = [_make_crossref_item(f"10.1234/{i}", f"Paper {i}", 2023) for i in range(1000)]
    page2_items = [
        _make_crossref_item(f"10.1234/{i}", f"Paper {i}", 2023) for i in range(1000, 2000)
    ]
    page3_items = [
        _make_crossref_item(f"10.1234/{i}", f"Paper {i}", 2023) for i in range(2000, 2500)
    ]

    page1_response = _make_crossref_response(page1_items, 2500, "cursor_page2")
    page2_response = _make_crossref_response(page2_items, 2500, "cursor_page3")
    page3_response = _make_crossref_response(page3_items, 2500, None)

    call_count = 0

    async def mock_get(url: str, headers: dict | None = None):
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

    papers = []
    async for paper in provider.search(title("test")):
        papers.append(paper)

    # Should have fetched all 2500 papers across 3 pages
    assert len(papers) == 2500
    assert call_count == 3


@pytest.mark.asyncio
async def test_search_single_page_when_results_fit():
    """CrossRef search should not paginate when results fit in single page."""
    from unittest.mock import MagicMock

    provider = CrossRef()

    items = [_make_crossref_item(f"10.1234/{i}", f"Paper {i}", 2023) for i in range(50)]
    response = _make_crossref_response(items, 50, None)

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
