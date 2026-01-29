# tests/test_cache.py
"""Tests for the PaperCache class."""

import pytest

from scimesh.cache import PaperCache
from scimesh.download import Downloader, download_papers


class TestPaperCache:
    """Tests for PaperCache initialization and directory creation."""

    def test_default_cache_dir(self, tmp_path, monkeypatch):
        """Test that default cache directory is in home directory."""
        # Mock Path.home() to return tmp_path
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        cache = PaperCache()

        assert cache.cache_dir == tmp_path / ".scimesh" / "cache"
        assert cache.pdf_dir == tmp_path / ".scimesh" / "cache" / "pdfs"
        assert cache.text_dir == tmp_path / ".scimesh" / "cache" / "text"

    def test_custom_cache_dir(self, tmp_path):
        """Test using custom cache directory."""
        custom_dir = tmp_path / "my_cache"
        cache = PaperCache(cache_dir=custom_dir)

        assert cache.cache_dir == custom_dir
        assert cache.pdf_dir == custom_dir / "pdfs"
        assert cache.text_dir == custom_dir / "text"

    def test_directories_created_on_init(self, tmp_path):
        """Test that cache directories are created on initialization."""
        cache_dir = tmp_path / "new_cache"
        assert not cache_dir.exists()

        cache = PaperCache(cache_dir=cache_dir)

        assert cache.pdf_dir.exists()
        assert cache.text_dir.exists()


class TestMakeSafeFilename:
    """Tests for _make_safe_filename method."""

    def test_basic_doi(self, tmp_path):
        """Test basic DOI sanitization."""
        cache = PaperCache(cache_dir=tmp_path)
        assert cache._make_safe_filename("10.1234/paper.v1") == "10.1234_paper.v1"

    def test_slash_replacement(self, tmp_path):
        """Test that slashes are replaced with underscores."""
        cache = PaperCache(cache_dir=tmp_path)
        assert cache._make_safe_filename("10.1234/abc/def") == "10.1234_abc_def"

    def test_backslash_replacement(self, tmp_path):
        """Test that backslashes are replaced."""
        cache = PaperCache(cache_dir=tmp_path)
        assert cache._make_safe_filename("10.1234\\paper") == "10.1234_paper"

    def test_colon_replacement(self, tmp_path):
        """Test that colons are replaced."""
        cache = PaperCache(cache_dir=tmp_path)
        assert cache._make_safe_filename("10.1234:paper") == "10.1234_paper"

    def test_special_characters_replacement(self, tmp_path):
        """Test that special characters are replaced."""
        cache = PaperCache(cache_dir=tmp_path)
        # Asterisk
        assert cache._make_safe_filename("10.1234*paper") == "10.1234_paper"
        # Question mark
        assert cache._make_safe_filename("10.1234?paper") == "10.1234_paper"
        # Double quotes
        assert cache._make_safe_filename('10.1234"paper') == "10.1234_paper"
        # Angle brackets
        assert cache._make_safe_filename("10.1234<paper>") == "10.1234_paper_"
        # Pipe
        assert cache._make_safe_filename("10.1234|paper") == "10.1234_paper"

    def test_multiple_invalid_chars(self, tmp_path):
        """Test DOI with multiple invalid characters."""
        cache = PaperCache(cache_dir=tmp_path)
        result = cache._make_safe_filename('10.1234/pa:per*v1?"test"')
        assert result == "10.1234_pa_per_v1__test_"

    def test_real_world_dois(self, tmp_path):
        """Test with real-world DOI formats."""
        cache = PaperCache(cache_dir=tmp_path)
        # Nature article DOI format
        assert cache._make_safe_filename("10.1038/nature12373") == "10.1038_nature12373"
        # PLoS ONE DOI format
        assert (
            cache._make_safe_filename("10.1371/journal.pone.0123456")
            == "10.1371_journal.pone.0123456"
        )
        # arXiv DOI format
        assert cache._make_safe_filename("10.48550/arXiv.2301.00001") == "10.48550_arXiv.2301.00001"

    def test_very_long_doi_uses_hash(self, tmp_path):
        """Test that very long DOIs are handled with hashing."""
        cache = PaperCache(cache_dir=tmp_path)
        long_doi = "10.1234/" + "a" * 300
        result = cache._make_safe_filename(long_doi)
        # Should be truncated and have a hash suffix
        assert len(result) <= 200
        assert "_" in result[-20:]  # Hash suffix separated by underscore


class TestPDFCache:
    """Tests for PDF caching functionality."""

    def test_has_pdf_false_when_not_cached(self, tmp_path):
        """Test has_pdf returns False for uncached PDF."""
        cache = PaperCache(cache_dir=tmp_path)
        assert cache.has_pdf("10.1234/paper") is False

    def test_has_pdf_true_after_save(self, tmp_path):
        """Test has_pdf returns True after saving PDF."""
        cache = PaperCache(cache_dir=tmp_path)
        cache.save_pdf("10.1234/paper", b"%PDF-1.4 test content")
        assert cache.has_pdf("10.1234/paper") is True

    def test_get_pdf_path_returns_none_when_not_cached(self, tmp_path):
        """Test get_pdf_path returns None for uncached PDF."""
        cache = PaperCache(cache_dir=tmp_path)
        assert cache.get_pdf_path("10.1234/paper") is None

    def test_get_pdf_path_returns_path_after_save(self, tmp_path):
        """Test get_pdf_path returns correct path after saving."""
        cache = PaperCache(cache_dir=tmp_path)
        saved_path = cache.save_pdf("10.1234/paper", b"%PDF-1.4 test")

        retrieved_path = cache.get_pdf_path("10.1234/paper")
        assert retrieved_path is not None
        assert retrieved_path == saved_path
        assert retrieved_path.exists()

    def test_save_and_retrieve_pdf(self, tmp_path):
        """Test saving and retrieving PDF content."""
        cache = PaperCache(cache_dir=tmp_path)
        pdf_content = b"%PDF-1.4 test content with binary data \x00\x01\x02"

        saved_path = cache.save_pdf("10.1234/paper", pdf_content)

        # Verify file was saved correctly
        assert saved_path.exists()
        assert saved_path.read_bytes() == pdf_content
        assert saved_path.suffix == ".pdf"

    def test_save_pdf_returns_correct_path(self, tmp_path):
        """Test that save_pdf returns the correct path."""
        cache = PaperCache(cache_dir=tmp_path)
        path = cache.save_pdf("10.1234/paper", b"test")

        expected_path = cache.pdf_dir / "10.1234_paper.pdf"
        assert path == expected_path

    def test_save_pdf_overwrites_existing(self, tmp_path):
        """Test that save_pdf overwrites existing cached PDF."""
        cache = PaperCache(cache_dir=tmp_path)

        cache.save_pdf("10.1234/paper", b"original content")
        cache.save_pdf("10.1234/paper", b"new content")

        path = cache.get_pdf_path("10.1234/paper")
        assert path is not None
        assert path.read_bytes() == b"new content"


class TestTextCache:
    """Tests for text caching functionality."""

    def test_has_text_false_when_not_cached(self, tmp_path):
        """Test has_text returns False for uncached text."""
        cache = PaperCache(cache_dir=tmp_path)
        assert cache.has_text("10.1234/paper") is False

    def test_has_text_true_after_save(self, tmp_path):
        """Test has_text returns True after saving text."""
        cache = PaperCache(cache_dir=tmp_path)
        cache.save_text("10.1234/paper", "Extracted text content")
        assert cache.has_text("10.1234/paper") is True

    def test_get_text_returns_none_when_not_cached(self, tmp_path):
        """Test get_text returns None for uncached text."""
        cache = PaperCache(cache_dir=tmp_path)
        assert cache.get_text("10.1234/paper") is None

    def test_get_text_returns_content_after_save(self, tmp_path):
        """Test get_text returns correct content after saving."""
        cache = PaperCache(cache_dir=tmp_path)
        text_content = "This is the extracted text from the paper."

        cache.save_text("10.1234/paper", text_content)
        retrieved = cache.get_text("10.1234/paper")

        assert retrieved == text_content

    def test_save_and_retrieve_unicode_text(self, tmp_path):
        """Test saving and retrieving Unicode text."""
        cache = PaperCache(cache_dir=tmp_path)
        unicode_text = "Unicode: \u00e9\u00e8\u00ea \u4e2d\u6587 \U0001f4da"

        cache.save_text("10.1234/paper", unicode_text)
        retrieved = cache.get_text("10.1234/paper")

        assert retrieved == unicode_text

    def test_save_text_returns_correct_path(self, tmp_path):
        """Test that save_text returns the correct path."""
        cache = PaperCache(cache_dir=tmp_path)
        path = cache.save_text("10.1234/paper", "test")

        expected_path = cache.text_dir / "10.1234_paper.txt"
        assert path == expected_path

    def test_save_text_overwrites_existing(self, tmp_path):
        """Test that save_text overwrites existing cached text."""
        cache = PaperCache(cache_dir=tmp_path)

        cache.save_text("10.1234/paper", "original text")
        cache.save_text("10.1234/paper", "new text")

        retrieved = cache.get_text("10.1234/paper")
        assert retrieved == "new text"


class TestCacheClear:
    """Tests for cache clearing functionality."""

    def test_clear_removes_all_pdfs(self, tmp_path):
        """Test that clear removes all cached PDFs."""
        cache = PaperCache(cache_dir=tmp_path)

        cache.save_pdf("10.1234/paper1", b"pdf1")
        cache.save_pdf("10.1234/paper2", b"pdf2")
        cache.save_pdf("10.1234/paper3", b"pdf3")

        cache.clear()

        assert cache.has_pdf("10.1234/paper1") is False
        assert cache.has_pdf("10.1234/paper2") is False
        assert cache.has_pdf("10.1234/paper3") is False
        assert list(cache.pdf_dir.glob("*.pdf")) == []

    def test_clear_removes_all_text(self, tmp_path):
        """Test that clear removes all cached text."""
        cache = PaperCache(cache_dir=tmp_path)

        cache.save_text("10.1234/paper1", "text1")
        cache.save_text("10.1234/paper2", "text2")
        cache.save_text("10.1234/paper3", "text3")

        cache.clear()

        assert cache.has_text("10.1234/paper1") is False
        assert cache.has_text("10.1234/paper2") is False
        assert cache.has_text("10.1234/paper3") is False
        assert list(cache.text_dir.glob("*.txt")) == []

    def test_clear_removes_both_pdfs_and_text(self, tmp_path):
        """Test that clear removes both PDFs and text."""
        cache = PaperCache(cache_dir=tmp_path)

        cache.save_pdf("10.1234/paper", b"pdf content")
        cache.save_text("10.1234/paper", "text content")

        cache.clear()

        assert cache.has_pdf("10.1234/paper") is False
        assert cache.has_text("10.1234/paper") is False

    def test_clear_preserves_directories(self, tmp_path):
        """Test that clear preserves the cache directories."""
        cache = PaperCache(cache_dir=tmp_path)

        cache.save_pdf("10.1234/paper", b"pdf")
        cache.save_text("10.1234/paper", "text")

        cache.clear()

        assert cache.pdf_dir.exists()
        assert cache.text_dir.exists()

    def test_clear_on_empty_cache(self, tmp_path):
        """Test that clear works on empty cache."""
        cache = PaperCache(cache_dir=tmp_path)
        # Should not raise any errors
        cache.clear()
        assert cache.pdf_dir.exists()
        assert cache.text_dir.exists()


class TestCacheIsolation:
    """Tests for cache isolation between different paper IDs."""

    def test_different_papers_have_different_cache_entries(self, tmp_path):
        """Test that different papers have separate cache entries."""
        cache = PaperCache(cache_dir=tmp_path)

        cache.save_pdf("10.1234/paper1", b"pdf1")
        cache.save_pdf("10.1234/paper2", b"pdf2")
        cache.save_text("10.1234/paper1", "text1")
        cache.save_text("10.1234/paper2", "text2")

        # Each paper has its own cached files
        path1 = cache.get_pdf_path("10.1234/paper1")
        path2 = cache.get_pdf_path("10.1234/paper2")
        assert path1 is not None and path1.read_bytes() == b"pdf1"
        assert path2 is not None and path2.read_bytes() == b"pdf2"
        assert cache.get_text("10.1234/paper1") == "text1"
        assert cache.get_text("10.1234/paper2") == "text2"

    def test_pdf_and_text_caches_are_independent(self, tmp_path):
        """Test that PDF and text caches are independent."""
        cache = PaperCache(cache_dir=tmp_path)

        # Save only PDF
        cache.save_pdf("10.1234/paper", b"pdf content")
        assert cache.has_pdf("10.1234/paper") is True
        assert cache.has_text("10.1234/paper") is False

        # Save only text for different paper
        cache.save_text("10.1234/other", "text content")
        assert cache.has_pdf("10.1234/other") is False
        assert cache.has_text("10.1234/other") is True


class TestCacheIntegrationWithDownload:
    """Tests for cache integration with download module."""

    @pytest.fixture
    def mock_downloader(self):
        """Create a mock downloader for testing."""

        class MockDownloader(Downloader):
            name = "mock"

            def __init__(self, pdf_bytes: bytes | None = None):
                super().__init__()
                self.pdf_bytes = pdf_bytes
                self.download_calls = []

            async def download(self, doi: str) -> bytes | None:
                self.download_calls.append(doi)
                return self.pdf_bytes

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        return MockDownloader

    @pytest.mark.asyncio
    async def test_download_uses_cache_on_hit(self, mock_downloader, tmp_path):
        """Test that download returns from cache without calling downloader."""
        cache_dir = tmp_path / "cache"
        output_dir = tmp_path / "output"
        cache = PaperCache(cache_dir=cache_dir)

        # Pre-populate cache
        cached_content = b"%PDF-1.4 cached content"
        cache.save_pdf("10.1234/cached", cached_content)

        downloader = mock_downloader(pdf_bytes=b"new content")

        results = []
        async for result in download_papers(
            ["10.1234/cached"], output_dir, downloaders=[downloader], cache=cache
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].source == "cache"
        # Downloader should not have been called
        assert len(downloader.download_calls) == 0
        # Output file should have cached content
        assert (output_dir / "10.1234_cached.pdf").read_bytes() == cached_content

    @pytest.mark.asyncio
    async def test_download_saves_to_cache_on_miss(self, mock_downloader, tmp_path):
        """Test that successful download saves PDF to cache."""
        cache_dir = tmp_path / "cache"
        output_dir = tmp_path / "output"
        cache = PaperCache(cache_dir=cache_dir)

        pdf_content = b"%PDF-1.4 downloaded content"
        downloader = mock_downloader(pdf_bytes=pdf_content)

        # Not in cache initially
        assert cache.has_pdf("10.1234/new") is False

        results = []
        async for result in download_papers(
            ["10.1234/new"], output_dir, downloaders=[downloader], cache=cache
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].source == "mock"
        # Now should be in cache
        assert cache.has_pdf("10.1234/new") is True
        cached_path = cache.get_pdf_path("10.1234/new")
        assert cached_path is not None and cached_path.read_bytes() == pdf_content

    @pytest.mark.asyncio
    async def test_download_does_not_cache_on_failure(self, mock_downloader, tmp_path):
        """Test that failed download does not add to cache."""
        cache_dir = tmp_path / "cache"
        output_dir = tmp_path / "output"
        cache = PaperCache(cache_dir=cache_dir)

        downloader = mock_downloader(pdf_bytes=None)  # Returns None = failure

        results = []
        async for result in download_papers(
            ["10.1234/failed"], output_dir, downloaders=[downloader], cache=cache
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0].success is False
        # Should not be in cache
        assert cache.has_pdf("10.1234/failed") is False

    @pytest.mark.asyncio
    async def test_download_with_use_cache_false(self, mock_downloader, tmp_path):
        """Test that use_cache=False bypasses cache entirely."""
        cache_dir = tmp_path / "cache"
        output_dir = tmp_path / "output"
        cache = PaperCache(cache_dir=cache_dir)

        # Pre-populate cache
        cache.save_pdf("10.1234/paper", b"cached content")

        pdf_content = b"%PDF-1.4 fresh download"
        downloader = mock_downloader(pdf_bytes=pdf_content)

        results = []
        async for result in download_papers(
            ["10.1234/paper"], output_dir, downloaders=[downloader], use_cache=False
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].source == "mock"  # Not "cache"
        # Downloader was called
        assert len(downloader.download_calls) == 1
        # Output file should have fresh content
        assert (output_dir / "10.1234_paper.pdf").read_bytes() == pdf_content
