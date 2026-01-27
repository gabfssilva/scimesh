# tests/test_search.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from scimesh.models import Author, Paper
from scimesh.query.combinators import title
from scimesh.search import search, take


@pytest.fixture
def mock_paper():
    return Paper(
        title="Test Paper",
        authors=(Author(name="Test Author"),),
        year=2020,
        source="mock",
        doi="10.1234/test",
    )


@pytest.fixture
def mock_provider(mock_paper):
    provider = MagicMock()
    provider.name = "mock"

    async def mock_search(query, max_results=100):
        yield mock_paper

    provider.search = mock_search
    provider.__aenter__ = AsyncMock(return_value=provider)
    provider.__aexit__ = AsyncMock(return_value=None)
    return provider


@pytest.mark.asyncio
async def test_search_single_provider(mock_provider, mock_paper):
    result = await search(title("test"), providers=[mock_provider])
    assert len(result.papers) == 1
    assert result.papers[0] == mock_paper


@pytest.mark.asyncio
async def test_search_with_string_query(mock_provider):
    result = await search("TITLE(test)", providers=[mock_provider])
    assert len(result.papers) == 1


@pytest.mark.asyncio
async def test_search_deduplicates_by_default(mock_paper):
    provider1 = MagicMock()
    provider1.name = "p1"
    provider2 = MagicMock()
    provider2.name = "p2"

    async def search1(q, max_results=100):
        yield mock_paper

    async def search2(q, max_results=100):
        # Same DOI, different source
        yield Paper(
            title="Test Paper Copy",
            authors=(),
            year=2020,
            source="p2",
            doi="10.1234/test",
        )

    provider1.search = search1
    provider2.search = search2
    provider1.__aenter__ = AsyncMock(return_value=provider1)
    provider1.__aexit__ = AsyncMock()
    provider2.__aenter__ = AsyncMock(return_value=provider2)
    provider2.__aexit__ = AsyncMock()

    result = await search(title("test"), providers=[provider1, provider2])
    assert len(result.papers) == 1


@pytest.mark.asyncio
async def test_search_no_dedupe():
    provider1 = MagicMock()
    provider1.name = "p1"
    provider2 = MagicMock()
    provider2.name = "p2"

    paper = Paper(title="Test", authors=(), year=2020, source="p1", doi="10.1/a")

    async def search1(q, max_results=100):
        yield paper

    async def search2(q, max_results=100):
        yield Paper(title="Test Copy", authors=(), year=2020, source="p2", doi="10.1/a")

    provider1.search = search1
    provider2.search = search2
    provider1.__aenter__ = AsyncMock(return_value=provider1)
    provider1.__aexit__ = AsyncMock()
    provider2.__aenter__ = AsyncMock(return_value=provider2)
    provider2.__aexit__ = AsyncMock()

    result = await search(title("test"), providers=[provider1, provider2], dedupe=False)
    assert len(result.papers) == 2


@pytest.mark.asyncio
async def test_search_on_error_fail():
    provider = MagicMock()
    provider.name = "failing"

    async def failing_search(q, max_results=100):
        raise ValueError("API Error")
        yield  # type: ignore

    provider.search = failing_search
    provider.__aenter__ = AsyncMock(return_value=provider)
    provider.__aexit__ = AsyncMock(return_value=False)

    with pytest.raises(ValueError, match="API Error"):
        await search(title("test"), providers=[provider], on_error="fail")


@pytest.mark.asyncio
async def test_search_on_error_ignore():
    provider = MagicMock()
    provider.name = "failing"

    async def failing_search(q):
        raise ValueError("API Error")
        yield  # type: ignore

    provider.search = failing_search
    provider.__aenter__ = AsyncMock(return_value=provider)
    provider.__aexit__ = AsyncMock(return_value=False)

    # on_error="ignore" should complete without raising, returning empty results
    result = await search(title("test"), providers=[provider], on_error="ignore")
    assert len(result.papers) == 0


@pytest.mark.asyncio
async def test_search_tracks_totals(mock_provider, mock_paper):
    result = await search(title("test"), providers=[mock_provider])
    assert result.total_by_provider["mock"] == 1


@pytest.mark.asyncio
async def test_search_stream_yields_papers(mock_provider, mock_paper):
    """Test that search with stream=True yields papers as they arrive."""
    papers = []
    async for paper in search(title("test"), providers=[mock_provider], stream=True):
        papers.append(paper)
    assert len(papers) == 1
    assert papers[0] == mock_paper


@pytest.mark.asyncio
async def test_search_stream_multiple_providers():
    """Test streaming from multiple providers."""
    provider1 = MagicMock()
    provider1.name = "p1"
    provider2 = MagicMock()
    provider2.name = "p2"

    paper1 = Paper(title="Paper 1", authors=(), year=2020, source="p1")
    paper2 = Paper(title="Paper 2", authors=(), year=2021, source="p2")

    async def search1(q, max_results=100):
        yield paper1

    async def search2(q, max_results=100):
        yield paper2

    provider1.search = search1
    provider2.search = search2
    provider1.__aenter__ = AsyncMock(return_value=provider1)
    provider1.__aexit__ = AsyncMock()
    provider2.__aenter__ = AsyncMock(return_value=provider2)
    provider2.__aexit__ = AsyncMock()

    papers = []
    async for paper in search(title("test"), providers=[provider1, provider2], stream=True):
        papers.append(paper)

    assert len(papers) == 2
    titles = {p.title for p in papers}
    assert titles == {"Paper 1", "Paper 2"}


@pytest.mark.asyncio
async def test_take_limits_items():
    """Test that take limits the number of items yielded."""

    async def infinite():
        i = 0
        while True:
            yield i
            i += 1

    items = [x async for x in take(5, infinite())]
    assert items == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_take_with_fewer_items():
    """Test take when iterator has fewer items than n."""

    async def finite():
        for i in range(3):
            yield i

    items = [x async for x in take(10, finite())]
    assert items == [0, 1, 2]


@pytest.mark.asyncio
async def test_take_zero():
    """Test take with n=0 yields nothing."""

    async def some_items():
        yield 1
        yield 2

    items = [x async for x in take(0, some_items())]
    assert items == []
