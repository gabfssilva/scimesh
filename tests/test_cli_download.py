"""Tests for the download, text and cache commands."""

import json
from io import StringIO

import pytest

from scimesh.cache import Cache
from scimesh.cli import (
    _extract_arxiv_doi_from_url,
    _parse_ids_from_file,
    _parse_ids_from_stdin,
    app,
)
from scimesh.download.base import Downloader

PDF = b"%PDF-1.4 fake"


class FakeDownloader(Downloader):
    def __init__(self, content: bytes | None = PDF):
        super().__init__()
        self.name = "fake"
        self.content = content
        self.calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def download(self, doi: str) -> bytes | None:
        self.calls.append(doi)
        return self.content


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIMESH_HOME", str(tmp_path / "scimesh"))
    return tmp_path


@pytest.fixture
def downloader(monkeypatch):
    fake = FakeDownloader()
    monkeypatch.setattr("scimesh.api.create_downloaders", lambda *_, **__: [fake])
    return fake


def run(*args: str) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        app(list(args))
    return exit_info.value.code


def pipe_stdin(monkeypatch, content: str) -> None:
    stdin = StringIO(content)
    stdin.isatty = lambda: False  # type: ignore[method-assign]
    monkeypatch.setattr("sys.stdin", stdin)


class TestIdParsing:
    def test_arxiv_doi_from_abs_url(self):
        doi = _extract_arxiv_doi_from_url("https://arxiv.org/abs/1908.06954v2")
        assert doi == "10.48550/arXiv.1908.06954"

    def test_arxiv_doi_from_pdf_url(self):
        doi = _extract_arxiv_doi_from_url("https://arxiv.org/pdf/1706.03762")
        assert doi == "10.48550/arXiv.1706.03762"

    def test_no_url(self):
        assert _extract_arxiv_doi_from_url(None) is None
        assert _extract_arxiv_doi_from_url("https://example.com/paper") is None

    def test_file_skips_blanks_and_comments(self, tmp_path):
        path = tmp_path / "dois.txt"
        path.write_text("# comment\n10.1234/a\n\n10.1234/b\n")

        assert _parse_ids_from_file(path) == ["10.1234/a", "10.1234/b"]

    def test_stdin_json(self, monkeypatch):
        pipe_stdin(
            monkeypatch,
            json.dumps(
                {"papers": [{"doi": "10.1234/a"}, {"url": "https://arxiv.org/abs/1706.03762"}]}
            ),
        )

        assert _parse_ids_from_stdin() == ["10.1234/a", "10.48550/arXiv.1706.03762"]

    def test_stdin_invalid_json(self, monkeypatch):
        pipe_stdin(monkeypatch, "not json")

        assert _parse_ids_from_stdin() == []


class TestDownload:
    def test_single_doi(self, home, downloader, tmp_path, capsys):
        output = tmp_path / "pdfs"

        assert run("download", "10.1234/paper", "-o", str(output)) == 0

        assert (output / "10.1234_paper.pdf").read_bytes() == PDF
        assert "Downloaded: 1/1" in capsys.readouterr().out

    def test_from_file(self, home, downloader, tmp_path):
        ids = tmp_path / "dois.txt"
        ids.write_text("10.1234/a\n10.1234/b\n")
        output = tmp_path / "pdfs"

        assert run("download", "--from", str(ids), "-o", str(output)) == 0

        assert sorted(p.name for p in output.glob("*.pdf")) == ["10.1234_a.pdf", "10.1234_b.pdf"]

    def test_from_stdin(self, home, downloader, tmp_path, monkeypatch):
        pipe_stdin(monkeypatch, json.dumps({"papers": [{"doi": "10.1234/a"}]}))
        output = tmp_path / "pdfs"

        assert run("download", "-o", str(output)) == 0

        assert (output / "10.1234_a.pdf").exists()

    def test_missing_file(self, home, tmp_path, capsys):
        assert run("download", "--from", str(tmp_path / "absent.txt")) == 1
        assert "File not found" in capsys.readouterr().err

    def test_no_ids(self, home, monkeypatch, capsys):
        pipe_stdin(monkeypatch, "")

        assert run("download") == 1
        assert "No papers provided" in capsys.readouterr().err

    def test_reports_failures(self, home, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(
            "scimesh.api.create_downloaders", lambda *_, **__: [FakeDownloader(content=None)]
        )

        assert run("download", "10.1234/paper", "-o", str(tmp_path / "pdfs")) == 0

        out = capsys.readouterr().out
        assert "not found" in out
        assert "Downloaded: 0/1" in out

    def test_second_run_reuses_the_cache(self, home, downloader, tmp_path):
        output = tmp_path / "pdfs"

        run("download", "10.1234/paper", "-o", str(output))
        run("download", "10.1234/paper", "-o", str(output))

        assert downloader.calls == ["10.1234/paper"]

    def test_extract_caches_text(self, home, downloader, monkeypatch, tmp_path):
        monkeypatch.setattr("scimesh.api.extract_markdown", lambda path: "# Extracted")

        assert run("download", "10.1234/paper", "-o", str(tmp_path / "pdfs"), "--extract") == 0

        with Cache() as cache:
            assert cache.text("10.1234/paper") == "# Extracted"


class TestText:
    def test_prints_markdown(self, home, downloader, monkeypatch, capsys):
        monkeypatch.setattr("scimesh.api.extract_markdown", lambda path: "# Extracted")

        assert run("text", "10.1234/paper") == 0
        assert "# Extracted" in capsys.readouterr().out

    def test_writes_to_file(self, home, downloader, monkeypatch, tmp_path):
        monkeypatch.setattr("scimesh.api.extract_markdown", lambda path: "# Extracted")
        output = tmp_path / "paper.md"

        assert run("text", "10.1234/paper", "-o", str(output)) == 0
        assert output.read_text() == "# Extracted"

    def test_without_pdf(self, home, monkeypatch, capsys):
        monkeypatch.setattr(
            "scimesh.api.create_downloaders", lambda *_, **__: [FakeDownloader(content=None)]
        )

        assert run("text", "10.1234/paper") == 1
        assert "No text available" in capsys.readouterr().err


class TestCacheCommands:
    def test_stats(self, home, capsys):
        with Cache() as cache:
            cache.save_pdf("10.1234/a", PDF, source="open_access")
            cache.save_text("10.1234/a", "body", extractor="v1")

        assert run("cache", "stats") == 0

        out = capsys.readouterr().out
        assert "PDFs:      1" in out
        assert "Texts:     1" in out

    def test_search(self, home, capsys):
        with Cache() as cache:
            cache.save_text("10.1234/a", "transformers attend", extractor="v1")

        assert run("cache", "search", "transformers") == 0
        assert "10.1234/a" in capsys.readouterr().out

    def test_gc(self, home, capsys):
        with Cache() as cache:
            cache.save_pdf("10.1234/a", PDF, source="open_access").unlink()

        assert run("cache", "gc") == 0
        assert "Dropped rows: 1" in capsys.readouterr().out

    def test_clear(self, home, capsys):
        with Cache() as cache:
            cache.save_pdf("10.1234/a", PDF, source="open_access")

        assert run("cache", "clear") == 0
        assert "Cleared 1 PDFs" in capsys.readouterr().out

        with Cache() as cache:
            assert cache.stats().documents == 0
