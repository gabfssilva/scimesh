"""Tests for the search, get and citations commands."""

from unittest.mock import patch

import pytest

from scimesh.cli import app
from scimesh.models import Author, Paper

PAPER = Paper(
    title="Test Paper",
    authors=(Author(name="Test Author"),),
    year=2020,
    source="arxiv",
    doi="10.1234/test",
)


def streams(*papers: Paper):
    """Side effect returning an async generator of papers."""

    def side_effect(*_, **__):
        async def gen():
            for paper in papers:
                yield paper

        return gen()

    return side_effect


@pytest.fixture
def search_stream():
    with patch("scimesh.api.search") as mock:
        mock.side_effect = streams(PAPER)
        yield mock


def run(*args: str) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        app(list(args))
    return exit_info.value.code


class TestSearch:
    def test_help(self):
        assert run("search", "--help") == 0

    def test_csv_to_stdout(self, search_stream, capsys):
        assert run("search", "TITLE(test)", "-p", "arxiv", "-f", "csv") == 0
        assert "Test Paper" in capsys.readouterr().out

    def test_multiple_providers(self, search_stream):
        assert run("search", "TITLE(test)", "-p", "arxiv", "-p", "openalex", "-f", "csv") == 0

        providers = search_stream.call_args.kwargs["providers"]
        assert [p.name for p in providers] == ["arxiv", "openalex"]

    def test_comma_separated_providers(self, search_stream):
        assert run("search", "TITLE(test)", "-p", "arxiv,openalex", "-f", "csv") == 0

        providers = search_stream.call_args.kwargs["providers"]
        assert [p.name for p in providers] == ["arxiv", "openalex"]

    def test_unknown_provider(self, capsys):
        assert run("search", "TITLE(test)", "-p", "nope") == 1
        assert "Unknown providers" in capsys.readouterr().err

    def test_unknown_format(self):
        assert run("search", "TITLE(test)", "-f", "nope") == 1

    def test_workspace_format_is_gone(self, capsys):
        assert run("search", "TITLE(test)", "-f", "workspace") == 1
        assert "Unknown export format" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("format", "expected"),
        [
            ("csv", "Test Paper"),
            ("json", '"title": "Test Paper"'),
            ("bibtex", "@"),
            ("ris", "TY  -"),
        ],
    )
    def test_output_file(self, search_stream, tmp_path, format, expected):
        output = tmp_path / f"results.{format}"

        assert run("search", "TITLE(test)", "-f", format, "-o", str(output)) == 0
        assert expected in output.read_text()

    def test_max_results_truncates(self, tmp_path):
        papers = [
            Paper(title=f"P{i}", authors=(), year=2020, source="arxiv", doi=f"10.1234/{i}")
            for i in range(10)
        ]
        output = tmp_path / "results.json"

        with patch("scimesh.api.search") as mock:
            mock.side_effect = streams(*papers)
            assert run("search", "TITLE(test)", "-n", "3", "-f", "json", "-o", str(output)) == 0

        assert output.read_text().count('"title"') == 3

    def test_caps_at_a_hundred_by_default(self, tmp_path):
        papers = [
            Paper(title=f"P{i}", authors=(), year=2020, source="arxiv", doi=f"10.1234/{i}")
            for i in range(150)
        ]
        output = tmp_path / "results.json"

        with patch("scimesh.api.search") as mock:
            mock.side_effect = streams(*papers)
            assert run("search", "TITLE(test)", "-f", "json", "-o", str(output)) == 0

        assert output.read_text().count('"title"') == 100

    def test_no_dedupe(self, search_stream):
        assert run("search", "TITLE(test)", "--no-dedupe", "-f", "csv") == 0
        assert search_stream.call_args.kwargs["dedupe"] is False

    @patch("sys.stdout.isatty", return_value=True)
    def test_tree_is_default_on_a_terminal(self, _isatty, search_stream, capsys):
        assert run("search", "TITLE(test)") == 0

        out = capsys.readouterr().out
        assert "Test Paper" in out
        assert "Year: 2020" in out

    @patch("sys.stdout.isatty", return_value=False)
    def test_json_when_piped(self, _isatty, search_stream, capsys):
        assert run("search", "TITLE(test)") == 0

        out = capsys.readouterr().out
        assert '"papers"' in out
        assert '"title": "Test Paper"' in out


class TestGet:
    def test_prints_the_paper(self, capsys):
        with patch("scimesh.api.Scimesh.get", return_value=PAPER):
            assert run("get", "10.1234/test", "-f", "csv") == 0

        assert "Test Paper" in capsys.readouterr().out

    def test_not_found(self, capsys):
        with patch("scimesh.api.Scimesh.get", return_value=None):
            assert run("get", "10.1234/missing") == 1

        assert "not found" in capsys.readouterr().err.lower()


class TestCitations:
    def test_prints_citing_papers(self, capsys):
        with patch("scimesh.api.Scimesh.citations") as mock:
            mock.side_effect = streams(PAPER)
            assert run("citations", "10.1234/test", "-d", "in", "-f", "csv") == 0

        assert mock.call_args.kwargs["direction"] == "in"
        assert "Test Paper" in capsys.readouterr().out

    def test_no_citations(self, capsys):
        with patch("scimesh.api.Scimesh.citations") as mock:
            mock.side_effect = streams()
            assert run("citations", "10.1234/test") == 0

        assert "No citations found" in capsys.readouterr().err

    def test_invalid_direction(self):
        assert run("citations", "10.1234/test", "-d", "sideways") != 0
