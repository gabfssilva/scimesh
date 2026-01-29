# tests/test_arxiv.py
import time
from unittest.mock import MagicMock

import pytest

from scimesh.providers.arxiv import ATOM_NS, Arxiv
from scimesh.query.combinators import abstract, author, fulltext, title, year


def test_translate_title():
    provider = Arxiv()
    q = title("transformer")
    result = provider._translate_query(q)
    assert result == 'ti:"transformer"'


def test_translate_author():
    provider = Arxiv()
    q = author("Vaswani")
    result = provider._translate_query(q)
    assert result == 'au:"Vaswani"'


def test_translate_abstract():
    provider = Arxiv()
    q = abstract("attention mechanism")
    result = provider._translate_query(q)
    assert result == 'abs:"attention mechanism"'


def test_translate_fulltext():
    provider = Arxiv()
    q = fulltext("neural network")
    result = provider._translate_query(q)
    assert result == 'all:"neural network"'


def test_translate_and():
    provider = Arxiv()
    q = title("BERT") & author("Google")
    result = provider._translate_query(q)
    assert result == '(ti:"BERT" AND au:"Google")'


def test_translate_or():
    provider = Arxiv()
    q = title("BERT") | title("GPT")
    result = provider._translate_query(q)
    assert result == '(ti:"BERT" OR ti:"GPT")'


def test_translate_not():
    provider = Arxiv()
    q = title("neural") & ~author("Smith")
    result = provider._translate_query(q)
    assert result == '(ti:"neural" ANDNOT au:"Smith")'


def test_translate_year_ignored():
    provider = Arxiv()
    q = year(2020, 2024)
    result = provider._translate_query(q)
    assert result == ""  # arXiv doesn't support year in query


def test_no_api_key_needed():
    provider = Arxiv()
    assert provider._api_key is None


def _make_arxiv_entry(arxiv_id: str, title_text: str) -> str:
    """Create an arXiv entry XML element."""
    return f"""
    <entry xmlns="{ATOM_NS[1:-1]}" xmlns:arxiv="http://arxiv.org/schemas/atom">
        <id>http://arxiv.org/abs/{arxiv_id}</id>
        <title>{title_text}</title>
        <published>2023-01-15T00:00:00Z</published>
        <author><name>Test Author</name></author>
        <summary>Test abstract for {title_text}</summary>
        <link href="http://arxiv.org/abs/{arxiv_id}" type="text/html"/>
        <arxiv:primary_category term="cs.AI"/>
    </entry>
    """


def _make_arxiv_response(entries: list[str], total_results: int, start: int) -> str:
    """Create a mock arXiv API response with OpenSearch metadata."""
    entries_xml = "\n".join(entries)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
    <opensearch:totalResults>{total_results}</opensearch:totalResults>
    <opensearch:startIndex>{start}</opensearch:startIndex>
    <opensearch:itemsPerPage>{len(entries)}</opensearch:itemsPerPage>
    {entries_xml}
</feed>"""


@pytest.mark.asyncio
async def test_search_paginates_with_delay():
    """arXiv search should paginate with 3 second delay between requests."""
    provider = Arxiv()

    # Create 2 pages of results (100 + 50 = 150 total)
    page1_entries = [_make_arxiv_entry(f"2023.{i:05d}", f"Paper {i}") for i in range(100)]
    page2_entries = [_make_arxiv_entry(f"2023.{i:05d}", f"Paper {i}") for i in range(100, 150)]

    page1_response = _make_arxiv_response(page1_entries, 150, 0)
    page2_response = _make_arxiv_response(page2_entries, 150, 100)

    call_count = 0
    call_times: list[float] = []

    async def mock_get(url: str):
        nonlocal call_count
        call_count += 1
        call_times.append(time.monotonic())
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        if call_count == 1:
            mock_response.text = page1_response
        else:
            mock_response.text = page2_response

        return mock_response

    mock_client = MagicMock()
    mock_client.get = mock_get

    provider._client = mock_client

    papers = []
    async for paper in provider.search(title("test")):
        papers.append(paper)

    # Should have fetched all 150 papers across 2 pages
    assert len(papers) == 150

    # Should have made exactly 2 API calls
    assert call_count == 2

    # Should have at least 3 second delay between calls
    assert len(call_times) == 2
    delay = call_times[1] - call_times[0]
    assert delay >= 3.0, f"Expected >= 3.0 second delay, got {delay:.2f}s"


@pytest.mark.asyncio
async def test_search_single_page_no_delay():
    """arXiv search should not delay when results fit in single page."""
    provider = Arxiv()

    # Create a single page of results
    entries = [_make_arxiv_entry(f"2023.{i:05d}", f"Paper {i}") for i in range(50)]
    response = _make_arxiv_response(entries, 50, 0)

    call_count = 0

    async def mock_get(url: str):
        nonlocal call_count
        call_count += 1
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = response
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
async def test_search_respects_arxiv_hard_limit(monkeypatch):
    """arXiv search should stop at 30000 (arXiv hard limit)."""
    import scimesh.providers.arxiv as arxiv_module

    # Mock asyncio.sleep to avoid waiting 15+ minutes
    async def mock_sleep(seconds):
        pass

    monkeypatch.setattr(arxiv_module.asyncio, "sleep", mock_sleep)

    provider = Arxiv()

    # Simulate a query with 35000 total results
    entries = [_make_arxiv_entry(f"2023.{i:05d}", f"Paper {i}") for i in range(100)]

    call_count = 0

    async def mock_get(url: str):
        nonlocal call_count
        call_count += 1
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Always return 35000 as total, but we should stop at 30000
        start = (call_count - 1) * 100
        mock_response.text = _make_arxiv_response(entries, 35000, start)
        return mock_response

    mock_client = MagicMock()
    mock_client.get = mock_get

    provider._client = mock_client

    papers = []
    async for paper in provider.search(title("test")):
        papers.append(paper)

    # Should stop at 30000 (300 pages * 100 per page)
    # 30000 / 100 = 300 pages
    assert call_count == 300
    assert len(papers) == 30000
