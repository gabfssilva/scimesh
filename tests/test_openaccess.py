# tests/test_openaccess.py
"""Tests for OpenAccessDownloader."""

import httpx
import pytest

from scimesh.download.openaccess import OpenAccessDownloader


class TestOpenAccessDownloaderInit:
    """Tests for OpenAccessDownloader initialization."""

    def test_requires_unpaywall_email_env_var(self, monkeypatch):
        """Should raise ValueError if UNPAYWALL_EMAIL is not set."""
        monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
        with pytest.raises(ValueError, match="UNPAYWALL_EMAIL"):
            OpenAccessDownloader()

    def test_accepts_unpaywall_email_from_env(self, monkeypatch):
        """Should initialize successfully when UNPAYWALL_EMAIL is set."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
        downloader = OpenAccessDownloader()
        assert downloader.email == "test@example.com"

    def test_has_correct_name(self, monkeypatch):
        """Should have name 'open_access'."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
        downloader = OpenAccessDownloader()
        assert downloader.name == "open_access"


class TestUnpaywallURLConstruction:
    """Tests for Unpaywall API URL construction."""

    def test_constructs_correct_unpaywall_url(self, monkeypatch):
        """Should construct correct Unpaywall API URL."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "researcher@university.edu")
        downloader = OpenAccessDownloader()
        doi = "10.1234/example.doi"
        expected = (
            "https://api.unpaywall.org/v2/10.1234/example.doi?email=researcher@university.edu"
        )
        assert downloader._unpaywall_url(doi) == expected

    def test_handles_special_characters_in_doi(self, monkeypatch):
        """Should handle DOIs with special characters."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
        downloader = OpenAccessDownloader()
        doi = "10.1000/xyz123"
        url = downloader._unpaywall_url(doi)
        assert "10.1000/xyz123" in url
        assert "email=test@example.com" in url


class TestArxivFallback:
    """Tests for arXiv fallback logic."""

    def test_extracts_arxiv_id_from_doi(self, monkeypatch):
        """Should extract arXiv ID from arXiv DOI."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
        downloader = OpenAccessDownloader()
        doi = "10.48550/arXiv.2301.12345"
        arxiv_id = downloader._extract_arxiv_id(doi)
        assert arxiv_id == "2301.12345"

    def test_extracts_arxiv_id_from_lowercase_doi(self, monkeypatch):
        """Should extract arXiv ID from lowercase arXiv DOI."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
        downloader = OpenAccessDownloader()
        doi = "10.48550/arxiv.1502.03044"
        arxiv_id = downloader._extract_arxiv_id(doi)
        assert arxiv_id == "1502.03044"

    def test_returns_none_for_non_arxiv_doi(self, monkeypatch):
        """Should return None for non-arXiv DOIs."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
        downloader = OpenAccessDownloader()
        doi = "10.1234/regular.doi"
        arxiv_id = downloader._extract_arxiv_id(doi)
        assert arxiv_id is None

    def test_constructs_correct_arxiv_pdf_url(self, monkeypatch):
        """Should construct correct arXiv PDF URL."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
        downloader = OpenAccessDownloader()
        arxiv_id = "2301.12345"
        expected = "https://arxiv.org/pdf/2301.12345.pdf"
        assert downloader._arxiv_pdf_url(arxiv_id) == expected


@pytest.mark.asyncio
class TestDownload:
    """Tests for the download method."""

    async def test_raises_runtime_error_without_context_manager(self, monkeypatch):
        """Should raise RuntimeError when called without context manager."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
        downloader = OpenAccessDownloader()
        with pytest.raises(RuntimeError, match="must be used as async context manager"):
            await downloader.download("10.1234/test.doi")

    async def test_downloads_pdf_from_unpaywall(self, monkeypatch):
        """Should download PDF from Unpaywall oa_locations."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

        unpaywall_response = {
            "oa_locations": [
                {"url_for_pdf": "https://example.com/paper.pdf"},
            ]
        }
        pdf_content = b"%PDF-1.4 fake pdf content"

        async with OpenAccessDownloader() as downloader:
            # Mock the HTTP client - use MagicMock for sync methods
            from unittest.mock import MagicMock

            mock_response_unpaywall = MagicMock()
            mock_response_unpaywall.status_code = 200
            mock_response_unpaywall.json.return_value = unpaywall_response

            mock_response_pdf = MagicMock()
            mock_response_pdf.status_code = 200
            mock_response_pdf.content = pdf_content

            async def mock_get(url, **kwargs):
                if "unpaywall.org" in url:
                    return mock_response_unpaywall
                return mock_response_pdf

            assert downloader._client is not None
            downloader._client.get = mock_get

            result = await downloader.download("10.1234/test.doi")
            assert result == pdf_content

    async def test_tries_multiple_oa_locations(self, monkeypatch):
        """Should try multiple oa_locations if first fails."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

        unpaywall_response = {
            "oa_locations": [
                {"url_for_pdf": None},  # No PDF URL
                {"url_for_pdf": "https://example.com/paper.pdf"},
            ]
        }
        pdf_content = b"%PDF-1.4 fake pdf content"

        async with OpenAccessDownloader() as downloader:
            from unittest.mock import MagicMock

            mock_response_unpaywall = MagicMock()
            mock_response_unpaywall.status_code = 200
            mock_response_unpaywall.json.return_value = unpaywall_response

            mock_response_pdf = MagicMock()
            mock_response_pdf.status_code = 200
            mock_response_pdf.content = pdf_content

            async def mock_get(url, **kwargs):
                if "unpaywall.org" in url:
                    return mock_response_unpaywall
                return mock_response_pdf

            assert downloader._client is not None
            downloader._client.get = mock_get

            result = await downloader.download("10.1234/test.doi")
            assert result == pdf_content

    async def test_falls_back_to_arxiv_when_unpaywall_fails(self, monkeypatch):
        """Should fall back to arXiv for arXiv DOIs when Unpaywall fails."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

        unpaywall_response = {"oa_locations": []}
        pdf_content = b"%PDF-1.4 arxiv pdf content"

        async with OpenAccessDownloader() as downloader:
            from unittest.mock import MagicMock

            mock_response_unpaywall = MagicMock()
            mock_response_unpaywall.status_code = 200
            mock_response_unpaywall.json.return_value = unpaywall_response

            mock_response_pdf = MagicMock()
            mock_response_pdf.status_code = 200
            mock_response_pdf.content = pdf_content

            call_urls = []

            async def mock_get(url, **kwargs):
                call_urls.append(url)
                if "unpaywall.org" in url:
                    return mock_response_unpaywall
                return mock_response_pdf

            assert downloader._client is not None
            downloader._client.get = mock_get

            result = await downloader.download("10.48550/arXiv.2301.12345")
            assert result == pdf_content
            # Should have called arXiv URL
            assert any("arxiv.org/pdf/2301.12345.pdf" in url for url in call_urls)

    async def test_returns_none_when_no_pdf_available(self, monkeypatch):
        """Should return None when no PDF is available."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

        unpaywall_response = {"oa_locations": []}

        async with OpenAccessDownloader() as downloader:
            from unittest.mock import MagicMock

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = unpaywall_response

            async def mock_get(url, **kwargs):
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get

            result = await downloader.download("10.1234/no.pdf.here")
            assert result is None

    async def test_returns_none_when_unpaywall_returns_404(self, monkeypatch):
        """Should return None when Unpaywall returns 404."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

        async with OpenAccessDownloader() as downloader:
            from unittest.mock import MagicMock

            mock_response = MagicMock()
            mock_response.status_code = 404

            async def mock_get(url, **kwargs):
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get

            result = await downloader.download("10.1234/not.found")
            assert result is None

    async def test_follows_redirects_when_downloading_pdf(self, monkeypatch):
        """Should follow redirects when downloading PDF."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

        unpaywall_response = {
            "oa_locations": [
                {"url_for_pdf": "https://example.com/redirect-to-pdf"},
            ]
        }
        pdf_content = b"%PDF-1.4 fake pdf content"

        async with OpenAccessDownloader() as downloader:
            from unittest.mock import MagicMock

            mock_response_unpaywall = MagicMock()
            mock_response_unpaywall.status_code = 200
            mock_response_unpaywall.json.return_value = unpaywall_response

            mock_response_pdf = MagicMock()
            mock_response_pdf.status_code = 200
            mock_response_pdf.content = pdf_content

            captured_kwargs = {}

            async def mock_get(url, **kwargs):
                captured_kwargs.update(kwargs)
                if "unpaywall.org" in url:
                    return mock_response_unpaywall
                return mock_response_pdf

            assert downloader._client is not None
            downloader._client.get = mock_get

            await downloader.download("10.1234/test.doi")
            # Verify follow_redirects is passed when downloading PDF
            assert captured_kwargs.get("follow_redirects") is True

    async def test_returns_none_on_network_error(self, monkeypatch):
        """Should return None when a network error occurs."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

        async with OpenAccessDownloader() as downloader:

            async def mock_get(url, **kwargs):
                raise httpx.RequestError("Connection failed")

            assert downloader._client is not None
            downloader._client.get = mock_get

            result = await downloader.download("10.1234/test.doi")
            assert result is None

    async def test_returns_none_on_malformed_json(self, monkeypatch):
        """Should return None when Unpaywall returns malformed JSON."""
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

        async with OpenAccessDownloader() as downloader:
            import json
            from unittest.mock import MagicMock

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("error", "doc", 0)

            async def mock_get(url, **kwargs):
                return mock_response

            assert downloader._client is not None
            downloader._client.get = mock_get

            result = await downloader.download("10.1234/test.doi")
            assert result is None
