# tests/test_scopus.py
from unittest.mock import MagicMock

import pytest

from scimesh.providers.scopus import Scopus
from scimesh.query.combinators import abstract, author, doi, fulltext, keyword, title, year


def test_translate_title():
    provider = Scopus()
    q = title("transformer")
    result = provider._translate_query(q)
    assert result == "TITLE(transformer)"


def test_translate_author():
    provider = Scopus()
    q = author("Vaswani")
    result = provider._translate_query(q)
    assert result == "AUTH(Vaswani)"


def test_translate_abstract():
    provider = Scopus()
    q = abstract("attention mechanism")
    result = provider._translate_query(q)
    assert result == "ABS(attention mechanism)"


def test_translate_keyword():
    provider = Scopus()
    q = keyword("machine learning")
    result = provider._translate_query(q)
    assert result == "KEY(machine learning)"


def test_translate_fulltext():
    provider = Scopus()
    q = fulltext("neural network")
    result = provider._translate_query(q)
    assert result == "ALL(neural network)"


def test_translate_doi():
    provider = Scopus()
    q = doi("10.1234/example")
    result = provider._translate_query(q)
    assert result == "DOI(10.1234/example)"


def test_translate_and():
    provider = Scopus()
    q = title("BERT") & author("Google")
    result = provider._translate_query(q)
    assert result == "(TITLE(BERT) AND AUTH(Google))"


def test_translate_or():
    provider = Scopus()
    q = title("BERT") | title("GPT")
    result = provider._translate_query(q)
    assert result == "(TITLE(BERT) OR TITLE(GPT))"


def test_translate_not():
    provider = Scopus()
    q = ~title("survey")
    result = provider._translate_query(q)
    assert result == "NOT TITLE(survey)"


def test_translate_year_range():
    provider = Scopus()
    q = year(2020, 2024)
    result = provider._translate_query(q)
    assert "PUBYEAR" in result
    # Should include years 2020-2024 inclusive
    assert "PUBYEAR > 2019" in result
    assert "PUBYEAR < 2025" in result


def test_translate_year_single():
    provider = Scopus()
    q = year(2023, 2023)
    result = provider._translate_query(q)
    assert result == "PUBYEAR = 2023"


def test_translate_year_start_only():
    provider = Scopus()
    q = year(start=2020)
    result = provider._translate_query(q)
    assert result == "PUBYEAR > 2019"


def test_translate_year_end_only():
    provider = Scopus()
    q = year(end=2024)
    result = provider._translate_query(q)
    assert result == "PUBYEAR < 2025"


def test_translate_complex_query():
    provider = Scopus()
    q = (title("deep learning") & author("LeCun")) | keyword("CNN")
    result = provider._translate_query(q)
    assert "TITLE(deep learning)" in result
    assert "AUTH(LeCun)" in result
    assert "KEY(CNN)" in result
    assert "AND" in result
    assert "OR" in result


def test_loads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("SCOPUS_API_KEY", "test-key-123")
    provider = Scopus()
    assert provider._api_key == "test-key-123"


def test_explicit_api_key_overrides_env(monkeypatch):
    monkeypatch.setenv("SCOPUS_API_KEY", "env-key")
    provider = Scopus(api_key="explicit-key")
    assert provider._api_key == "explicit-key"


def test_no_api_key_returns_none():
    # Clear any existing env var
    import os

    original = os.environ.pop("SCOPUS_API_KEY", None)
    try:
        provider = Scopus()
        assert provider._api_key is None
    finally:
        if original:
            os.environ["SCOPUS_API_KEY"] = original


def test_provider_name():
    provider = Scopus()
    assert provider.name == "scopus"


def test_base_url():
    provider = Scopus()
    assert provider.BASE_URL == "https://api.elsevier.com/content/search/scopus"


def test_page_size_constant():
    """Scopus provider should have PAGE_SIZE constant of 25."""
    provider = Scopus()
    assert provider.PAGE_SIZE == 25


# Helper functions for mocking Scopus responses


def _make_scopus_entry(entry_id: int, title_text: str, year: int) -> dict:
    """Create a minimal Scopus entry object."""
    return {
        "dc:identifier": f"SCOPUS_ID:{entry_id}",
        "dc:title": title_text,
        "prism:coverDate": f"{year}-01-01",
        "dc:creator": "Test Author",
        "prism:doi": f"10.1234/test{entry_id}",
        "prism:publicationName": "Test Journal",
        "citedby-count": "10",
        "link": [
            {
                "@ref": "self",
                "@href": f"https://api.elsevier.com/content/abstract/scopus_id/{entry_id}",
            },
            {
                "@ref": "scopus",
                "@href": f"https://www.scopus.com/record/display.uri?eid={entry_id}",
            },
        ],
        "openaccessFlag": False,
    }


def _make_scopus_response(
    entries: list[dict],
    total: int,
    next_cursor: str | None,
    self_cursor: str = "*",
) -> dict:
    """Create a mock Scopus API response with pagination links."""
    links = [
        {
            "@ref": "self",
            "@href": f"https://api.elsevier.com/content/search/scopus?cursor={self_cursor}",
        },
    ]
    if next_cursor:
        links.append(
            {
                "@ref": "next",
                "@href": f"https://api.elsevier.com/content/search/scopus?cursor={next_cursor}",
            }
        )
    return {
        "search-results": {
            "opensearch:totalResults": str(total),
            "opensearch:startIndex": "0",
            "opensearch:itemsPerPage": str(len(entries)),
            "link": links,
            "entry": entries,
        }
    }


@pytest.mark.asyncio
async def test_search_paginates_with_cursor():
    """Scopus search should paginate using cursor-based pagination."""
    provider = Scopus(api_key="test-api-key")

    # Create 3 pages of results (25 + 25 + 10 = 60 total)
    page1_entries = [_make_scopus_entry(i, f"Paper {i}", 2023) for i in range(25)]
    page2_entries = [_make_scopus_entry(i, f"Paper {i}", 2023) for i in range(25, 50)]
    page3_entries = [_make_scopus_entry(i, f"Paper {i}", 2023) for i in range(50, 60)]

    page1_response = _make_scopus_response(page1_entries, 60, "cursor_page2", "*")
    page2_response = _make_scopus_response(page2_entries, 60, "cursor_page3", "cursor_page2")
    page3_response = _make_scopus_response(page3_entries, 60, None, "cursor_page3")

    call_count = 0
    requested_urls = []

    async def mock_get(url: str, headers=None):
        nonlocal call_count
        call_count += 1
        requested_urls.append(url)
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

    # Should have fetched all 60 papers across 3 pages
    assert len(papers) == 60
    assert call_count == 3

    # Verify first request uses initial cursor "*"
    assert "cursor=%2A" in requested_urls[0] or "cursor=*" in requested_urls[0]
    # Verify subsequent requests use the cursor from previous response
    assert "cursor=cursor_page2" in requested_urls[1]
    assert "cursor=cursor_page3" in requested_urls[2]


@pytest.mark.asyncio
async def test_search_single_page_when_results_fit():
    """Scopus search should not paginate when results fit in single page."""
    provider = Scopus(api_key="test-api-key")

    entries = [_make_scopus_entry(i, f"Paper {i}", 2023) for i in range(10)]
    response = _make_scopus_response(entries, 10, None)

    call_count = 0

    async def mock_get(url: str, headers=None):
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

    assert len(papers) == 10
    assert call_count == 1
