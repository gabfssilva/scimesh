# tests/test_cli_download.py
import json
from io import StringIO
from unittest.mock import patch

import pytest

from scimesh.cli import (
    _extract_arxiv_doi_from_url,
    _parse_dois_from_file,
    _parse_dois_from_stdin,
    app,
)
from scimesh.download import DownloadResult


@pytest.fixture(autouse=True)
def set_unpaywall_email(monkeypatch):
    """Set UNPAYWALL_EMAIL for all tests in this module."""
    monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")


@pytest.fixture
def mock_download_results():
    """Fixture providing sample download results."""

    async def _generator(dois, output_dir, downloaders=None):
        for doi in dois:
            if "fail" in doi:
                yield DownloadResult(
                    doi=doi,
                    success=False,
                    error="not found",
                )
            else:
                yield DownloadResult(
                    doi=doi,
                    success=True,
                    filename=f"{doi.replace('/', '_')}.pdf",
                    source="open_access",
                )

    return _generator


# Test DOI parsing from positional argument
class TestPositionalDOI:
    @patch("scimesh.cli.download_papers")
    def test_single_doi_positional(self, mock_download, mock_download_results, tmp_path, capsys):
        """Test downloading with a single positional DOI argument."""
        mock_download.side_effect = mock_download_results

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "10.1234/paper", "-o", str(tmp_path)])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Downloading 1 papers" in captured.out
        assert "10.1234_paper.pdf" in captured.out
        assert "Downloaded: 1/1" in captured.out

    @patch("scimesh.cli.download_papers")
    def test_doi_with_special_chars(self, mock_download, mock_download_results, tmp_path, capsys):
        """Test DOI with special characters."""
        mock_download.side_effect = mock_download_results

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "10.1234/paper.v2", "-o", str(tmp_path)])

        assert exc_info.value.code == 0
        mock_download.assert_called_once()
        call_args = mock_download.call_args
        dois = list(call_args[0][0])
        assert dois == ["10.1234/paper.v2"]


# Test DOI parsing from file
class TestFileInput:
    def test_parse_dois_from_file(self, tmp_path):
        """Test parsing DOIs from a file."""
        doi_file = tmp_path / "dois.txt"
        doi_file.write_text("10.1234/paper1\n10.5678/paper2\n# comment\n\n10.9999/paper3\n")

        dois = _parse_dois_from_file(doi_file)

        assert dois == ["10.1234/paper1", "10.5678/paper2", "10.9999/paper3"]

    def test_parse_dois_from_file_empty_lines(self, tmp_path):
        """Test that empty lines are skipped."""
        doi_file = tmp_path / "dois.txt"
        doi_file.write_text("\n\n10.1234/paper\n\n")

        dois = _parse_dois_from_file(doi_file)

        assert dois == ["10.1234/paper"]

    def test_parse_dois_from_file_comments(self, tmp_path):
        """Test that comment lines are skipped."""
        doi_file = tmp_path / "dois.txt"
        doi_file.write_text("# This is a comment\n10.1234/paper\n# Another comment\n")

        dois = _parse_dois_from_file(doi_file)

        assert dois == ["10.1234/paper"]

    @patch("scimesh.cli.download_papers")
    def test_download_from_file(self, mock_download, mock_download_results, tmp_path, capsys):
        """Test downloading from a file with DOIs."""
        mock_download.side_effect = mock_download_results

        doi_file = tmp_path / "dois.txt"
        doi_file.write_text("10.1234/paper1\n10.5678/paper2\n")
        output_dir = tmp_path / "output"

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "--from", str(doi_file), "-o", str(output_dir)])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Downloading 2 papers" in captured.out
        assert "Downloaded: 2/2" in captured.out

    def test_download_from_nonexistent_file(self, tmp_path, capsys):
        """Test error when file does not exist."""
        output_dir = tmp_path / "output"

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "--from", str(tmp_path / "nonexistent.txt"), "-o", str(output_dir)])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "File not found" in captured.err


# Test stdin detection logic
class TestStdinInput:
    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdin.isatty", return_value=False)
    def test_parse_dois_from_stdin_json(self, mock_isatty, mock_stdin):
        """Test parsing DOIs from JSON stdin."""
        json_data = json.dumps(
            {
                "papers": [
                    {"doi": "10.1234/paper1", "title": "Paper 1"},
                    {"doi": "10.5678/paper2", "title": "Paper 2"},
                    {"title": "Paper without DOI"},
                ]
            }
        )
        mock_stdin.read = lambda: json_data
        # Need to re-patch stdin with the data
        with patch("sys.stdin", StringIO(json_data)):
            dois = _parse_dois_from_stdin()

        assert dois == ["10.1234/paper1", "10.5678/paper2"]

    @patch("sys.stdin", StringIO("invalid json"))
    def test_parse_dois_from_stdin_invalid_json(self):
        """Test handling of invalid JSON from stdin."""
        dois = _parse_dois_from_stdin()
        assert dois == []

    @patch("sys.stdin", StringIO('{"papers": []}'))
    def test_parse_dois_from_stdin_empty_papers(self):
        """Test handling of empty papers list."""
        dois = _parse_dois_from_stdin()
        assert dois == []

    def test_parse_dois_from_stdin_arxiv_url_fallback(self):
        """Test that arXiv URLs are converted to DOIs when DOI is missing."""
        json_data = json.dumps(
            {
                "papers": [
                    {"doi": "10.1234/real.doi", "url": "https://example.com"},
                    {"url": "https://arxiv.org/abs/1908.06954v2"},  # No DOI, has arXiv URL
                    {"url": "https://arxiv.org/pdf/2301.12345.pdf"},  # PDF URL format
                    {"url": "https://example.com/other"},  # Non-arXiv URL, no DOI
                ]
            }
        )
        with patch("sys.stdin", StringIO(json_data)):
            dois = _parse_dois_from_stdin()

        assert dois == [
            "10.1234/real.doi",
            "10.48550/arXiv.1908.06954",
            "10.48550/arXiv.2301.12345",
        ]


class TestArxivDoiExtraction:
    """Tests for arXiv URL to DOI conversion."""

    def test_extract_arxiv_doi_from_abs_url(self):
        """Test extracting DOI from arXiv abstract URL."""
        url = "https://arxiv.org/abs/1908.06954v2"
        assert _extract_arxiv_doi_from_url(url) == "10.48550/arXiv.1908.06954"

    def test_extract_arxiv_doi_from_pdf_url(self):
        """Test extracting DOI from arXiv PDF URL."""
        url = "https://arxiv.org/pdf/2301.12345.pdf"
        assert _extract_arxiv_doi_from_url(url) == "10.48550/arXiv.2301.12345"

    def test_extract_arxiv_doi_from_non_arxiv_url(self):
        """Test that non-arXiv URLs return None."""
        url = "https://example.com/paper"
        assert _extract_arxiv_doi_from_url(url) is None

    def test_extract_arxiv_doi_from_none(self):
        """Test that None URL returns None."""
        assert _extract_arxiv_doi_from_url(None) is None

    @patch("scimesh.cli.download_papers")
    @patch("scimesh.cli._parse_dois_from_stdin")
    @patch("sys.stdin.isatty", return_value=False)
    def test_download_from_stdin(
        self, mock_isatty, mock_parse, mock_download, mock_download_results, tmp_path, capsys
    ):
        """Test downloading from piped stdin."""
        mock_parse.return_value = ["10.1234/paper1", "10.5678/paper2"]
        mock_download.side_effect = mock_download_results

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "-o", str(tmp_path)])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Downloading 2 papers" in captured.out


# Test output formatting
class TestOutputFormatting:
    @patch("scimesh.cli.download_papers")
    def test_success_output_format(self, mock_download, mock_download_results, tmp_path, capsys):
        """Test output format for successful downloads."""
        mock_download.side_effect = mock_download_results

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "10.1234/paper", "-o", str(tmp_path)])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # Check checkmark symbol
        assert "\u2713" in captured.out or "✓" in captured.out
        assert "10.1234_paper.pdf" in captured.out
        assert "(open_access)" in captured.out

    @patch("scimesh.cli.download_papers")
    def test_failure_output_format(self, mock_download, tmp_path, capsys):
        """Test output format for failed downloads."""

        async def _failed_generator(dois, output_dir, downloaders=None):
            for doi in dois:
                yield DownloadResult(
                    doi=doi,
                    success=False,
                    error="not found",
                )

        mock_download.side_effect = _failed_generator

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "10.1234/fail", "-o", str(tmp_path)])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # Check X symbol
        assert "\u2717" in captured.out or "✗" in captured.out
        assert "not found" in captured.out
        assert "Downloaded: 0/1 | Failed: 1" in captured.out

    @patch("scimesh.cli.download_papers")
    def test_mixed_results_summary(self, mock_download, mock_download_results, tmp_path, capsys):
        """Test summary with mixed success/failure."""
        mock_download.side_effect = mock_download_results

        doi_file = tmp_path / "dois.txt"
        doi_file.write_text("10.1234/paper1\n10.5678/fail_paper\n10.9999/paper2\n")

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "--from", str(doi_file), "-o", str(tmp_path / "output")])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Downloaded: 2/3 | Failed: 1" in captured.out


# Test error cases
class TestErrorCases:
    @patch("sys.stdin.isatty", return_value=True)
    def test_no_dois_provided(self, mock_isatty, tmp_path, capsys):
        """Test error when no DOIs are provided."""
        with pytest.raises(SystemExit) as exc_info:
            app(["download", "-o", str(tmp_path)])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No DOIs provided" in captured.err

    def test_download_help(self, capsys):
        """Test that download command shows help."""
        with pytest.raises(SystemExit) as exc_info:
            app(["download", "--help"])
        assert exc_info.value.code == 0


# Test input source priority
class TestInputPriority:
    @patch("scimesh.cli.download_papers")
    @patch("scimesh.cli._parse_dois_from_stdin")
    @patch("sys.stdin.isatty", return_value=False)
    def test_file_takes_priority_over_stdin(
        self, mock_isatty, mock_parse_stdin, mock_download, mock_download_results, tmp_path, capsys
    ):
        """Test that --from file takes priority over stdin."""
        mock_parse_stdin.return_value = ["10.stdin/paper"]
        mock_download.side_effect = mock_download_results

        doi_file = tmp_path / "dois.txt"
        doi_file.write_text("10.file/paper\n")

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "--from", str(doi_file), "-o", str(tmp_path / "output")])

        assert exc_info.value.code == 0
        # Verify file DOIs were used, not stdin
        mock_download.assert_called_once()
        call_args = mock_download.call_args
        dois = list(call_args[0][0])
        assert dois == ["10.file/paper"]
        # Stdin parser should not have been called
        mock_parse_stdin.assert_not_called()

    @patch("scimesh.cli.download_papers")
    @patch("scimesh.cli._parse_dois_from_stdin")
    @patch("sys.stdin.isatty", return_value=False)
    def test_positional_takes_priority_over_stdin(
        self, mock_isatty, mock_parse_stdin, mock_download, mock_download_results, tmp_path, capsys
    ):
        """Test that positional DOI takes priority over stdin."""
        mock_parse_stdin.return_value = ["10.stdin/paper"]
        mock_download.side_effect = mock_download_results

        with pytest.raises(SystemExit) as exc_info:
            app(["download", "10.positional/paper", "-o", str(tmp_path)])

        assert exc_info.value.code == 0
        mock_download.assert_called_once()
        call_args = mock_download.call_args
        dois = list(call_args[0][0])
        assert dois == ["10.positional/paper"]
        mock_parse_stdin.assert_not_called()
