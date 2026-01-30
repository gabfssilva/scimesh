# tests/test_cli.py
from unittest.mock import patch

import pytest

from scimesh.cli import app
from scimesh.models import Author, Paper, SearchResult


@pytest.fixture
def mock_search_result():
    return SearchResult(
        papers=[
            Paper(
                title="Test Paper",
                authors=(Author(name="Test Author"),),
                year=2020,
                source="arxiv",
                doi="10.1234/test",
            )
        ],
        total_by_provider={"arxiv": 1},
    )


def make_search_side_effect(result: SearchResult):
    """Create a side_effect that returns coroutine for batch or async gen for stream."""

    async def batch_coro():
        return result

    async def stream_gen():
        for paper in result.papers:
            yield paper

    def side_effect(*args, **kwargs):
        if kwargs.get("stream", False):
            return stream_gen()
        return batch_coro()

    return side_effect


def test_cli_search_help(capsys):
    """Test that CLI shows help without errors."""
    with pytest.raises(SystemExit) as exc_info:
        app(["search", "--help"])
    assert exc_info.value.code == 0


@patch("scimesh.cli.do_search")
def test_cli_search_basic(mock_search, mock_search_result, capsys):
    """Test basic search with non-streaming format."""
    mock_search.side_effect = make_search_side_effect(mock_search_result)

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv", "-f", "csv"])

    assert exc_info.value.code == 0
    mock_search.assert_called_once()
    captured = capsys.readouterr()
    assert "Test Paper" in captured.out or "1 papers" in captured.err


@patch("scimesh.cli.do_search")
def test_cli_search_multiple_providers(mock_search, mock_search_result):
    """Test multiple providers with non-streaming format."""
    mock_search.side_effect = make_search_side_effect(mock_search_result)

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv", "-p", "openalex", "-f", "csv"])

    assert exc_info.value.code == 0
    call_args = mock_search.call_args
    providers = call_args.kwargs.get("providers") or call_args[1].get("providers")
    assert len(providers) == 2


@patch("scimesh.cli.do_search")
def test_cli_search_output_file(mock_search, mock_search_result, tmp_path):
    mock_search.side_effect = make_search_side_effect(mock_search_result)
    output_file = tmp_path / "results.csv"

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv", "-o", str(output_file)])

    assert exc_info.value.code == 0
    assert output_file.exists()


@patch("scimesh.cli.do_search")
def test_cli_search_json_format(mock_search, mock_search_result, tmp_path):
    mock_search.side_effect = make_search_side_effect(mock_search_result)
    output_file = tmp_path / "results.json"

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv", "-o", str(output_file), "-f", "json"])

    assert exc_info.value.code == 0
    assert output_file.exists()
    content = output_file.read_text()
    assert "Test Paper" in content


def test_cli_invalid_provider(capsys):
    """Test that invalid provider names cause an error."""
    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "invalid_provider"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Unknown providers" in captured.err


@patch("scimesh.cli.do_search")
def test_cli_search_with_max_results(mock_search, mock_search_result):
    """Test max results truncates results after search."""
    mock_search.side_effect = make_search_side_effect(mock_search_result)

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv", "-n", "50", "-f", "csv"])

    assert exc_info.value.code == 0
    # max_results is no longer passed to do_search - it's used to truncate results
    call_args = mock_search.call_args
    assert "max_results" not in call_args.kwargs


@patch("scimesh.cli.do_search")
def test_cli_search_no_dedupe(mock_search, mock_search_result):
    """Test no-dedupe with non-streaming format."""
    mock_search.side_effect = make_search_side_effect(mock_search_result)

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv", "--no-dedupe", "-f", "csv"])

    assert exc_info.value.code == 0
    call_args = mock_search.call_args
    dedupe = call_args.kwargs.get("dedupe")
    assert dedupe is False


@patch("scimesh.cli.do_search")
def test_cli_search_bibtex_format(mock_search, mock_search_result, tmp_path):
    mock_search.side_effect = make_search_side_effect(mock_search_result)
    output_file = tmp_path / "results.bib"

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv", "-o", str(output_file), "-f", "bibtex"])

    assert exc_info.value.code == 0
    assert output_file.exists()
    content = output_file.read_text()
    assert "@" in content  # BibTeX entries start with @


@patch("scimesh.cli.do_search")
def test_cli_search_ris_format(mock_search, mock_search_result, tmp_path):
    mock_search.side_effect = make_search_side_effect(mock_search_result)
    output_file = tmp_path / "results.ris"

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv", "-o", str(output_file), "-f", "ris"])

    assert exc_info.value.code == 0
    assert output_file.exists()
    content = output_file.read_text()
    assert "TY  -" in content  # RIS entries start with TY


def test_cli_invalid_format(capsys, tmp_path):
    """Test that invalid format causes an error."""
    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv", "-f", "invalid_format"])
    assert exc_info.value.code == 1


@patch("sys.stdout.isatty", return_value=True)
@patch("scimesh.cli.do_search")
def test_cli_search_tree_format_default(mock_search, mock_isatty, mock_search_result, capsys):
    """Test that tree format is the default with streaming in terminal."""
    mock_search.side_effect = make_search_side_effect(mock_search_result)

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    # Tree format shows paper title as root
    assert "Test Paper" in captured.out
    # And year as child
    assert "Year: 2020" in captured.out


@patch("sys.stdout.isatty", return_value=False)
@patch("scimesh.cli.do_search")
def test_cli_search_json_when_piped(mock_search, mock_isatty, mock_search_result, capsys):
    """Test that JSON format is used when stdout is piped."""
    mock_search.side_effect = make_search_side_effect(mock_search_result)

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "-p", "arxiv"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    # JSON format when piped
    assert '"papers"' in captured.out
    assert '"title": "Test Paper"' in captured.out


def test_search_vault_format_requires_output(capsys):
    """Vault format requires --output flag."""
    from scimesh.cli import app

    with pytest.raises(SystemExit) as exc_info:
        app(["search", "TITLE(test)", "--format", "vault"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "--output" in captured.err.lower() or "output" in captured.err.lower()
