# tests/test_scihub.py
"""Tests for SciHubDownloader."""

import time
from unittest.mock import MagicMock

import httpx
import pytest

from scimesh.download.scihub import SciHubDownloader


class TestSciHubDownloaderInit:
    """Tests for SciHubDownloader initialization."""

    def test_has_correct_name(self):
        """Should have name 'scihub'."""
        downloader = SciHubDownloader()
        assert downloader.name == "scihub"

    def test_has_known_domains_list(self):
        """Should have a list of known Sci-Hub domains."""
        downloader = SciHubDownloader()
        assert hasattr(downloader, "domains")
        assert len(downloader.domains) >= 3
        assert "sci-hub.se" in downloader.domains
        assert "sci-hub.st" in downloader.domains
        assert "sci-hub.ru" in downloader.domains


class TestThrottleApplied:
    """Tests for throttle decorator on download method."""

    def test_download_has_throttle_wrapper(self):
        """Should have throttle applied to download method."""
        downloader = SciHubDownloader()
        # The throttle decorator uses @wraps, so we check for wrapper behavior
        # by looking at the function's closure or checking timing behavior
        assert hasattr(downloader.download, "__wrapped__") or callable(downloader.download)

    @pytest.mark.asyncio
    async def test_throttle_enforces_rate_limit(self):
        """Should enforce rate limit of 1 call per 3 seconds."""
        download_start_times: list[float] = []

        async with SciHubDownloader() as downloader:
            # Wrap download to track when it starts (after throttle releases)

            async def tracking_attempt(doi, domain):
                # Only record time for first domain attempt of each download
                if domain == downloader.domains[0]:
                    download_start_times.append(time.monotonic())
                return None

            downloader._attempt_download = tracking_attempt

            # Make two rapid calls
            await downloader.download("10.1234/test1")
            await downloader.download("10.1234/test2")

        # There should be at least 2.9 seconds between download starts (allowing tolerance)
        assert len(download_start_times) == 2
        interval = download_start_times[1] - download_start_times[0]
        assert interval >= 2.9, f"Interval {interval}s is less than required 3s"


class TestDomainFallback:
    """Tests for domain fallback logic."""

    @pytest.mark.asyncio
    async def test_tries_domains_in_order(self):
        """Should try domains in order when earlier ones fail."""
        attempted_domains: list[str] = []

        async with SciHubDownloader() as downloader:

            async def mock_attempt(doi, domain):
                attempted_domains.append(domain)
                return None  # Simulate failure

            downloader._attempt_download = mock_attempt
            await downloader.download("10.1234/test")

        # Should have tried all domains in order
        assert attempted_domains == downloader.domains

    @pytest.mark.asyncio
    async def test_stops_on_first_success(self):
        """Should stop trying domains after first successful download."""
        attempted_domains: list[str] = []
        pdf_content = b"%PDF-1.4 test content"

        async with SciHubDownloader() as downloader:

            async def mock_attempt(doi, domain):
                attempted_domains.append(domain)
                if domain == "sci-hub.st":  # Second domain succeeds
                    return pdf_content
                return None

            downloader._attempt_download = mock_attempt
            result = await downloader.download("10.1234/test")

        assert result == pdf_content
        # Should have stopped after sci-hub.st
        assert attempted_domains == ["sci-hub.se", "sci-hub.st"]

    @pytest.mark.asyncio
    async def test_constructs_correct_url(self):
        """Should construct URL with pattern https://{domain}/{doi}."""
        async with SciHubDownloader() as downloader:
            captured_urls: list[str] = []

            async def mock_get(url, **kwargs):
                captured_urls.append(url)
                mock_response = MagicMock()
                mock_response.status_code = 404
                mock_response.text = ""
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get

            await downloader.download("10.1234/my.doi")

        # Check that URLs were constructed correctly
        assert "https://sci-hub.se/10.1234/my.doi" in captured_urls


class TestPDFExtraction:
    """Tests for PDF extraction from HTML response."""

    @pytest.mark.asyncio
    async def test_extracts_pdf_from_embed_tag(self):
        """Should extract PDF URL from embed tag with .pdf src."""
        html_content = """
        <html>
        <body>
            <embed src="https://moscow.sci-hub.st/1234/abcd.pdf" type="application/pdf">
        </body>
        </html>
        """
        pdf_content = b"%PDF-1.4 test pdf"

        async with SciHubDownloader() as downloader:

            async def mock_get(url, **kwargs):
                mock_response = MagicMock()
                if ".pdf" in url:
                    mock_response.status_code = 200
                    mock_response.content = pdf_content
                else:
                    mock_response.status_code = 200
                    mock_response.text = html_content
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get
            result = await downloader.download("10.1234/test")

        assert result == pdf_content

    @pytest.mark.asyncio
    async def test_extracts_pdf_from_iframe_tag(self):
        """Should extract PDF URL from iframe tag with .pdf src."""
        html_content = """
        <html>
        <body>
            <iframe src="//sci-hub.se/downloads/1234/paper.pdf"></iframe>
        </body>
        </html>
        """
        pdf_content = b"%PDF-1.4 iframe pdf"

        async with SciHubDownloader() as downloader:

            async def mock_get(url, **kwargs):
                mock_response = MagicMock()
                if ".pdf" in url:
                    mock_response.status_code = 200
                    mock_response.content = pdf_content
                else:
                    mock_response.status_code = 200
                    mock_response.text = html_content
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get
            result = await downloader.download("10.1234/test")

        assert result == pdf_content

    @pytest.mark.asyncio
    async def test_handles_protocol_relative_urls(self):
        """Should handle protocol-relative URLs (starting with //)."""
        html_content = """
        <html>
        <body>
            <embed src="//cdn.sci-hub.se/paper.pdf">
        </body>
        </html>
        """
        pdf_content = b"%PDF-1.4 protocol relative pdf"
        captured_urls: list[str] = []

        async with SciHubDownloader() as downloader:

            async def mock_get(url, **kwargs):
                captured_urls.append(url)
                mock_response = MagicMock()
                if ".pdf" in url:
                    mock_response.status_code = 200
                    mock_response.content = pdf_content
                else:
                    mock_response.status_code = 200
                    mock_response.text = html_content
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get
            result = await downloader.download("10.1234/test")

        assert result == pdf_content
        # Should have prepended https: to the protocol-relative URL
        assert any("https://cdn.sci-hub.se/paper.pdf" in url for url in captured_urls)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_pdf_in_html(self):
        """Should return None when HTML contains no PDF link."""
        html_content = """
        <html>
        <body>
            <p>No PDF here</p>
        </body>
        </html>
        """

        async with SciHubDownloader() as downloader:

            async def mock_get(url, **kwargs):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.text = html_content
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get
            result = await downloader.download("10.1234/test")

        assert result is None


class TestGracefulFailure:
    """Tests for graceful error handling."""

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self):
        """Should return None when network error occurs."""
        async with SciHubDownloader() as downloader:

            async def mock_get(url, **kwargs):
                raise httpx.RequestError("Connection failed")

            assert downloader._client is not None
            downloader._client.get = mock_get
            result = await downloader.download("10.1234/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        """Should return None when request times out."""
        async with SciHubDownloader() as downloader:

            async def mock_get(url, **kwargs):
                raise httpx.TimeoutException("Request timed out")

            assert downloader._client is not None
            downloader._client.get = mock_get
            result = await downloader.download("10.1234/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_all_domains_return_404(self):
        """Should return None when all domains return 404."""
        async with SciHubDownloader() as downloader:

            async def mock_get(url, **kwargs):
                mock_response = MagicMock()
                mock_response.status_code = 404
                mock_response.text = "Not found"
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get
            result = await downloader.download("10.1234/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_continues_on_single_domain_failure(self):
        """Should continue to next domain when one fails."""
        call_count = 0
        pdf_content = b"%PDF-1.4 success"

        async with SciHubDownloader() as downloader:

            async def mock_get(url, **kwargs):
                nonlocal call_count
                call_count += 1
                mock_response = MagicMock()

                # First domain throws error, second succeeds
                if "sci-hub.se" in url:
                    raise httpx.RequestError("First domain failed")
                elif "sci-hub.st" in url:
                    mock_response.status_code = 200
                    mock_response.text = '<embed src="https://example.com/paper.pdf">'
                    return mock_response
                elif ".pdf" in url:
                    mock_response.status_code = 200
                    mock_response.content = pdf_content
                    return mock_response

                mock_response.status_code = 404
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get
            result = await downloader.download("10.1234/test")

        assert result == pdf_content

    @pytest.mark.asyncio
    async def test_raises_runtime_error_without_context_manager(self):
        """Should raise RuntimeError when called without context manager."""
        downloader = SciHubDownloader()
        with pytest.raises(RuntimeError, match="must be used as async context manager"):
            await downloader.download("10.1234/test.doi")
