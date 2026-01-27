# tests/test_download_init.py
"""Tests for download module __init__.py functionality."""

import pytest

from scimesh.download import (
    Downloader,
    DownloadResult,
    download_papers,
    make_filename,
)


class TestDownloadResult:
    """Tests for DownloadResult dataclass."""

    def test_success_result(self):
        """Test creating a successful download result."""
        result = DownloadResult(
            doi="10.1234/paper.v1",
            success=True,
            filename="10.1234_paper.v1.pdf",
            source="open_access",
        )
        assert result.doi == "10.1234/paper.v1"
        assert result.success is True
        assert result.filename == "10.1234_paper.v1.pdf"
        assert result.source == "open_access"
        assert result.error is None

    def test_failure_result(self):
        """Test creating a failed download result."""
        result = DownloadResult(
            doi="10.1234/paper.v1",
            success=False,
            error="Download failed",
        )
        assert result.doi == "10.1234/paper.v1"
        assert result.success is False
        assert result.filename is None
        assert result.source is None
        assert result.error == "Download failed"

    def test_default_values(self):
        """Test that optional fields have correct defaults."""
        result = DownloadResult(doi="10.1234/test", success=True)
        assert result.filename is None
        assert result.source is None
        assert result.error is None


class TestMakeFilename:
    """Tests for make_filename function."""

    def test_basic_doi(self):
        """Test basic DOI sanitization."""
        assert make_filename("10.1234/paper.v1") == "10.1234_paper.v1"

    def test_slash_replacement(self):
        """Test that slashes are replaced with underscores."""
        assert make_filename("10.1234/abc/def") == "10.1234_abc_def"

    def test_backslash_replacement(self):
        """Test that backslashes are replaced."""
        assert make_filename("10.1234\\paper") == "10.1234_paper"

    def test_colon_replacement(self):
        """Test that colons are replaced."""
        assert make_filename("10.1234:paper") == "10.1234_paper"

    def test_asterisk_replacement(self):
        """Test that asterisks are replaced."""
        assert make_filename("10.1234*paper") == "10.1234_paper"

    def test_question_mark_replacement(self):
        """Test that question marks are replaced."""
        assert make_filename("10.1234?paper") == "10.1234_paper"

    def test_quote_replacement(self):
        """Test that double quotes are replaced."""
        assert make_filename('10.1234"paper') == "10.1234_paper"

    def test_angle_brackets_replacement(self):
        """Test that angle brackets are replaced."""
        assert make_filename("10.1234<paper>") == "10.1234_paper_"

    def test_pipe_replacement(self):
        """Test that pipes are replaced."""
        assert make_filename("10.1234|paper") == "10.1234_paper"

    def test_multiple_invalid_chars(self):
        """Test DOI with multiple invalid characters."""
        assert make_filename('10.1234/pa:per*v1?"test"') == "10.1234_pa_per_v1__test_"

    def test_doi_no_extension(self):
        """Test that make_filename does not add .pdf extension."""
        filename = make_filename("10.1234/paper")
        assert not filename.endswith(".pdf")

    def test_real_world_doi(self):
        """Test with a real-world DOI format."""
        # Nature article DOI format
        assert make_filename("10.1038/nature12373") == "10.1038_nature12373"
        # PLoS ONE DOI format
        assert make_filename("10.1371/journal.pone.0123456") == "10.1371_journal.pone.0123456"
        # arXiv DOI format
        assert make_filename("10.48550/arXiv.2301.00001") == "10.48550_arXiv.2301.00001"


class TestDownloadPapers:
    """Tests for download_papers async generator."""

    @pytest.fixture
    def mock_downloader(self):
        """Create a mock downloader for testing."""

        class MockDownloader(Downloader):
            name = "mock"

            def __init__(self, pdf_bytes: bytes | None = None, should_raise: bool = False):
                super().__init__()
                self.pdf_bytes = pdf_bytes
                self.should_raise = should_raise
                self.download_calls = []

            async def download(self, doi: str) -> bytes | None:
                self.download_calls.append(doi)
                if self.should_raise:
                    raise Exception("Mock download error")
                return self.pdf_bytes

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        return MockDownloader

    @pytest.mark.asyncio
    async def test_successful_download(self, mock_downloader, tmp_path):
        """Test successful paper download."""
        pdf_content = b"%PDF-1.4 test content"
        downloader = mock_downloader(pdf_bytes=pdf_content)

        results = []
        async for result in download_papers(
            ["10.1234/paper"], tmp_path, downloaders=[downloader], use_cache=False
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].doi == "10.1234/paper"
        assert results[0].filename == "10.1234_paper.pdf"
        assert results[0].source == "mock"
        assert results[0].error is None

        # Verify file was written
        expected_file = tmp_path / "10.1234_paper.pdf"
        assert expected_file.exists()
        assert expected_file.read_bytes() == pdf_content

    @pytest.mark.asyncio
    async def test_failed_download(self, mock_downloader, tmp_path):
        """Test failed paper download."""
        downloader = mock_downloader(pdf_bytes=None)

        results = []
        async for result in download_papers(
            ["10.1234/paper"], tmp_path, downloaders=[downloader], use_cache=False
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].doi == "10.1234/paper"
        assert results[0].filename is None
        assert results[0].source is None
        assert "All downloaders failed" in results[0].error

    @pytest.mark.asyncio
    async def test_multiple_dois(self, mock_downloader, tmp_path):
        """Test downloading multiple papers."""
        pdf_content = b"%PDF-1.4 test"
        downloader = mock_downloader(pdf_bytes=pdf_content)

        dois = ["10.1234/paper1", "10.1234/paper2", "10.1234/paper3"]
        results = []
        async for result in download_papers(
            dois, tmp_path, downloaders=[downloader], use_cache=False
        ):
            results.append(result)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.success is True
            assert result.doi == dois[i]

    @pytest.mark.asyncio
    async def test_fallback_to_second_downloader(self, mock_downloader, tmp_path):
        """Test that second downloader is tried when first fails."""
        pdf_content = b"%PDF-1.4 from second"
        first_downloader = mock_downloader(pdf_bytes=None)
        first_downloader.name = "first"
        second_downloader = mock_downloader(pdf_bytes=pdf_content)
        second_downloader.name = "second"

        results = []
        async for result in download_papers(
            ["10.1234/paper"],
            tmp_path,
            downloaders=[first_downloader, second_downloader],
            use_cache=False,
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].source == "second"

    @pytest.mark.asyncio
    async def test_downloader_exception_continues(self, mock_downloader, tmp_path):
        """Test that exception in one downloader tries next."""
        pdf_content = b"%PDF-1.4 success"
        failing_downloader = mock_downloader(should_raise=True)
        failing_downloader.name = "failing"
        success_downloader = mock_downloader(pdf_bytes=pdf_content)
        success_downloader.name = "success"

        results = []
        async for result in download_papers(
            ["10.1234/paper"],
            tmp_path,
            downloaders=[failing_downloader, success_downloader],
            use_cache=False,
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].source == "success"

    @pytest.mark.asyncio
    async def test_creates_output_directory(self, mock_downloader, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        pdf_content = b"%PDF-1.4 test"
        downloader = mock_downloader(pdf_bytes=pdf_content)
        output_dir = tmp_path / "nested" / "output" / "dir"

        assert not output_dir.exists()

        results = []
        async for result in download_papers(
            ["10.1234/paper"], output_dir, downloaders=[downloader], use_cache=False
        ):
            results.append(result)

        assert output_dir.exists()
        assert (output_dir / "10.1234_paper.pdf").exists()

    @pytest.mark.asyncio
    async def test_empty_dois_list(self, mock_downloader, tmp_path):
        """Test with empty DOIs list."""
        downloader = mock_downloader(pdf_bytes=b"test")

        results = []
        async for result in download_papers(
            [], tmp_path, downloaders=[downloader], use_cache=False
        ):
            results.append(result)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_yields_results_incrementally(self, mock_downloader, tmp_path):
        """Test that results are yielded one at a time."""
        pdf_content = b"%PDF-1.4 test"
        downloader = mock_downloader(pdf_bytes=pdf_content)

        dois = ["10.1234/paper1", "10.1234/paper2"]
        gen = download_papers(dois, tmp_path, downloaders=[downloader], use_cache=False)

        # Get first result
        result1 = await gen.__anext__()
        assert result1.doi == "10.1234/paper1"

        # Get second result
        result2 = await gen.__anext__()
        assert result2.doi == "10.1234/paper2"

        # Should be exhausted
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
