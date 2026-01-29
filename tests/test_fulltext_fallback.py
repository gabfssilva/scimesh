# tests/test_fulltext_fallback.py
"""Tests for the fulltext fallback mixin with auto-download."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from scimesh.download.base import Downloader
from scimesh.fulltext import FulltextIndex
from scimesh.models import Paper
from scimesh.providers._fulltext_fallback import FulltextFallbackMixin
from scimesh.query.combinators import Query, fulltext, title

if TYPE_CHECKING:
    pass


class MockDownloader(Downloader):
    """Mock downloader for testing."""

    name = "mock"

    def __init__(self, result: bytes | None = None):
        super().__init__()
        self._result = result

    async def download(self, doi: str) -> bytes | None:
        return self._result


class MockProvider(FulltextFallbackMixin):
    """Mock provider for testing the fulltext fallback mixin."""

    def __init__(self, papers: list[Paper], downloader: Downloader | None = None):
        self._papers = papers
        self._downloader = downloader

    async def _search_api(self, query: Query) -> AsyncIterator[Paper]:
        """Return mock papers."""
        for paper in self._papers:
            yield paper


@pytest.fixture
def temp_index(tmp_path):
    """Create a temporary fulltext index."""
    db_path = tmp_path / "test_fulltext.db"
    return FulltextIndex(db_path=db_path)


@pytest.fixture
def temp_cache(tmp_path):
    """Create a temporary cache directory."""
    from scimesh.cache import PaperCache

    return PaperCache(cache_dir=tmp_path / "cache")


@pytest.fixture
def sample_papers():
    """Create sample papers for testing."""
    return [
        Paper(
            title="Machine Learning Paper",
            authors=(),
            year=2023,
            source="test",
            doi="10.1234/ml-paper",
        ),
        Paper(
            title="Deep Learning Paper",
            authors=(),
            year=2023,
            source="test",
            doi="10.1234/dl-paper",
        ),
        Paper(
            title="Statistics Paper",
            authors=(),
            year=2023,
            source="test",
            doi="10.1234/stats-paper",
        ),
        Paper(
            title="No DOI Paper",
            authors=(),
            year=2023,
            source="test",
            doi=None,
        ),
    ]


class TestFulltextFallbackMixin:
    """Tests for FulltextFallbackMixin."""

    @pytest.mark.asyncio
    async def test_no_downloader_returns_only_indexed(self, temp_index, sample_papers):
        """When no downloader is provided, only pre-indexed papers are returned."""
        # Pre-index one paper
        temp_index.add("10.1234/ml-paper", "This paper discusses transformer neural networks.")

        provider = MockProvider(sample_papers, downloader=None)

        with patch("scimesh.providers._fulltext_fallback.FulltextIndex", return_value=temp_index):
            query = title("learning") & fulltext("transformer")
            results = []
            async for paper in provider._search_with_fulltext_filter(query):
                results.append(paper)

        # Only the pre-indexed paper should be returned
        assert len(results) == 1
        assert results[0].doi == "10.1234/ml-paper"

    @pytest.mark.asyncio
    async def test_with_downloader_downloads_and_indexes(
        self, temp_index, temp_cache, sample_papers
    ):
        """When downloader is provided, papers are downloaded and indexed."""
        downloader = MockDownloader(result=b"pdf content")
        provider = MockProvider(sample_papers, downloader=downloader)

        mock_text = "This is extracted text containing transformer architecture."

        with (
            patch("scimesh.providers._fulltext_fallback.FulltextIndex", return_value=temp_index),
            patch("scimesh.providers._fulltext_fallback.PaperCache", return_value=temp_cache),
        ):
            # Mock _try_download_single to return matching text
            async def mock_download(doi, *args, **kwargs):
                return mock_text

            with patch.object(provider, "_try_download_single", side_effect=mock_download):
                query = title("learning") & fulltext("transformer")
                results = []
                async for paper in provider._search_with_fulltext_filter(query):
                    results.append(paper)

        # Papers with DOIs that were downloaded and matched should be returned
        dois = [p.doi for p in results]
        assert "10.1234/ml-paper" in dois
        assert "10.1234/dl-paper" in dois
        assert "10.1234/stats-paper" in dois
        # No DOI paper should not be returned
        assert None not in dois

    @pytest.mark.asyncio
    async def test_download_failure_continues_gracefully(
        self, temp_index, temp_cache, sample_papers
    ):
        """When download fails, processing continues with other papers."""
        # Pre-index one paper
        temp_index.add("10.1234/ml-paper", "This paper discusses transformer neural networks.")

        downloader = MockDownloader(result=b"pdf content")
        provider = MockProvider(sample_papers, downloader=downloader)

        with (
            patch("scimesh.providers._fulltext_fallback.FulltextIndex", return_value=temp_index),
            patch("scimesh.providers._fulltext_fallback.PaperCache", return_value=temp_cache),
        ):
            # Mock _try_download_single to always fail (return None)
            async def mock_download_fail(doi, *args, **kwargs):
                return None

            with patch.object(provider, "_try_download_single", side_effect=mock_download_fail):
                query = title("learning") & fulltext("transformer")
                results = []
                async for paper in provider._search_with_fulltext_filter(query):
                    results.append(paper)

        # Should still return the pre-indexed paper
        assert len(results) == 1
        assert results[0].doi == "10.1234/ml-paper"

    @pytest.mark.asyncio
    async def test_streaming_processes_papers_individually(self, temp_index, temp_cache):
        """Test that papers are processed one by one (streaming)."""
        papers = [
            Paper(
                title=f"Paper {i}",
                authors=(),
                year=2023,
                source="test",
                doi=f"10.1234/paper-{i}",
            )
            for i in range(5)
        ]

        downloader = MockDownloader(result=b"pdf content")
        provider = MockProvider(papers, downloader=downloader)

        download_calls = []

        async def mock_download(doi, *args, **kwargs):
            download_calls.append(doi)
            return "Content with searchterm in it."

        with (
            patch("scimesh.providers._fulltext_fallback.FulltextIndex", return_value=temp_index),
            patch("scimesh.providers._fulltext_fallback.PaperCache", return_value=temp_cache),
            patch.object(provider, "_try_download_single", side_effect=mock_download),
        ):
            query = title("paper") & fulltext("searchterm")
            results = []
            async for paper in provider._search_with_fulltext_filter(query):
                results.append(paper)

        # All papers should have been processed
        assert len(download_calls) == 5
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_pre_indexed_papers_returned_immediately(self, temp_index, sample_papers):
        """Pre-indexed papers are returned immediately, others attempted for download."""
        # Pre-index papers that match
        temp_index.add("10.1234/ml-paper", "Content with transformer")
        temp_index.add("10.1234/dl-paper", "More transformer content")

        downloader = MockDownloader(result=b"pdf content")
        provider = MockProvider(sample_papers, downloader=downloader)

        download_calls: list[str] = []

        async def mock_download(doi: str, *args, **kwargs):
            download_calls.append(doi)
            return None

        with (
            patch("scimesh.providers._fulltext_fallback.FulltextIndex", return_value=temp_index),
            patch.object(provider, "_try_download_single", side_effect=mock_download),
        ):
            query = title("learning") & fulltext("transformer")
            results = []
            async for paper in provider._search_with_fulltext_filter(query):
                results.append(paper)

        # Pre-indexed papers should be returned
        assert len(results) == 2
        # Pre-indexed papers (ml-paper, dl-paper) should NOT be in download calls
        assert "10.1234/ml-paper" not in download_calls
        assert "10.1234/dl-paper" not in download_calls
        # Other papers should have been attempted
        assert "10.1234/stats-paper" in download_calls

    @pytest.mark.asyncio
    async def test_papers_without_doi_skipped_for_download(self, temp_index, temp_cache):
        """Papers without DOI are skipped during download phase."""
        papers = [
            Paper(title="No DOI 1", authors=(), year=2023, source="test", doi=None),
            Paper(title="No DOI 2", authors=(), year=2023, source="test", doi=None),
            Paper(title="Has DOI", authors=(), year=2023, source="test", doi="10.1234/with-doi"),
        ]

        downloader = MockDownloader(result=b"pdf content")
        provider = MockProvider(papers, downloader=downloader)

        download_dois = []

        async def mock_download(doi, *args, **kwargs):
            download_dois.append(doi)
            return "content matching fulltext"

        with (
            patch("scimesh.providers._fulltext_fallback.FulltextIndex", return_value=temp_index),
            patch("scimesh.providers._fulltext_fallback.PaperCache", return_value=temp_cache),
            patch.object(provider, "_try_download_single", side_effect=mock_download),
        ):
            query = title("doi") & fulltext("content")
            results = []
            async for paper in provider._search_with_fulltext_filter(query):
                results.append(paper)

        # Only the paper with DOI should have been downloaded
        assert download_dois == ["10.1234/with-doi"]
        assert len(results) == 1
        assert results[0].doi == "10.1234/with-doi"


class TestTextMatchesTerm:
    """Tests for _text_matches_term method."""

    def test_case_insensitive_match(self):
        """Test that matching is case-insensitive."""
        mixin = FulltextFallbackMixin()

        assert mixin._text_matches_term("This is TRANSFORMER text", "transformer")
        assert mixin._text_matches_term("This is transformer text", "TRANSFORMER")
        assert mixin._text_matches_term("TRANSFORMER", "transformer")

    def test_substring_match(self):
        """Test that substrings are matched."""
        mixin = FulltextFallbackMixin()

        assert mixin._text_matches_term("The transformers model", "transformer")
        assert mixin._text_matches_term("pre-transformer era", "transformer")

    def test_no_match(self):
        """Test that non-matching text returns False."""
        mixin = FulltextFallbackMixin()

        assert not mixin._text_matches_term("This is about CNN", "transformer")
        assert not mixin._text_matches_term("", "transformer")
