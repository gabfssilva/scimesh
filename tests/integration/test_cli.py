from __future__ import annotations

import csv
import json
import re
import subprocess
import tempfile
from io import StringIO
from pathlib import Path

from tests.integration.conftest import (
    ATTENTION_PAPER_DOI,
    ATTENTION_PAPER_YEAR,
)


def run_cli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "scimesh", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def parse_json_output(output: str) -> list[dict]:
    lines = output.strip().split("\n")
    json_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            json_start = i
            break
    json_str = "\n".join(lines[json_start:])
    data = json.loads(json_str)
    return data.get("papers", [])


class TestCliSearchDefaultOutput:
    def test_search_returns_success(self):
        result = run_cli("search", "TITLE(transformer)", "--provider", "arxiv", "--max", "3")
        assert result.returncode == 0

    def test_search_has_papers(self):
        result = run_cli("search", "TITLE(transformer)", "--provider", "arxiv", "--max", "3")
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        assert len(papers) >= 1

    def test_search_paper_has_all_fields(self):
        result = run_cli("search", "TITLE(neural network)", "--provider", "openalex", "--max", "3")
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        assert len(papers) >= 1

        for paper in papers:
            assert paper.get("title"), "Paper must have title"
            year = paper.get("year")
            assert year and 1900 <= year <= 2030, f"Invalid year: {year}"
            assert paper.get("authors") and len(paper["authors"]) >= 1, "Paper must have authors"

    def test_search_title_filter_respected(self):
        result = run_cli("search", "TITLE(self-attention)", "--provider", "arxiv", "--max", "5")
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        assert len(papers) >= 1

        for paper in papers:
            assert "attention" in paper["title"].lower(), (
                f"Title should contain 'attention': {paper['title']}"
            )

    def test_search_year_filter_respected(self):
        result = run_cli(
            "search",
            "TITLE(neural) AND PUBYEAR > 2020 AND PUBYEAR < 2023",
            "--provider",
            "openalex",
            "--max",
            "5",
        )
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        for paper in papers:
            year = paper.get("year")
            if year:
                assert 2021 <= year <= 2022, f"Year should be 2021-2022: {year}"

    def test_search_author_filter_respected(self):
        result = run_cli("search", "AUTHOR(Hinton)", "--provider", "openalex", "--max", "5")
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        assert len(papers) >= 1

        for paper in papers:
            author_names = " ".join(a["name"] for a in paper.get("authors", [])).lower()
            assert "hinton" in author_names, (
                f"Authors should contain 'Hinton': {paper.get('authors')}"
            )


class TestCliSearchJsonOutput:
    def test_json_is_valid(self):
        result = run_cli(
            "search",
            "TITLE(transformer)",
            "--provider",
            "arxiv",
            "--max",
            "3",
            "--format",
            "json",
        )
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        assert isinstance(papers, list)

    def test_json_has_required_fields(self):
        result = run_cli(
            "search",
            "TITLE(neural network)",
            "--provider",
            "openalex",
            "--max",
            "3",
            "--format",
            "json",
        )
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        assert len(papers) >= 1

        for paper in papers:
            assert "title" in paper
            assert "year" in paper
            assert "authors" in paper

    def test_json_respects_title_filter(self):
        result = run_cli(
            "search",
            "TITLE(self-attention)",
            "--provider",
            "arxiv",
            "--max",
            "5",
            "--format",
            "json",
        )
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        for paper in papers:
            assert "attention" in paper["title"].lower()

    def test_json_respects_year_filter(self):
        result = run_cli(
            "search",
            "TITLE(learning) AND PUBYEAR > 2020 AND PUBYEAR < 2023",
            "--provider",
            "openalex",
            "--max",
            "5",
            "--format",
            "json",
        )
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        for paper in papers:
            if paper["year"]:
                assert 2021 <= paper["year"] <= 2022


class TestCliSearchCsvOutput:
    def test_csv_is_valid(self):
        result = run_cli(
            "search",
            "TITLE(transformer)",
            "--provider",
            "arxiv",
            "--max",
            "3",
            "--format",
            "csv",
        )
        assert result.returncode == 0

        reader = csv.DictReader(StringIO(result.stdout))
        rows = list(reader)
        assert len(rows) >= 1

    def test_csv_has_required_columns(self):
        result = run_cli(
            "search",
            "TITLE(neural network)",
            "--provider",
            "openalex",
            "--max",
            "3",
            "--format",
            "csv",
        )
        assert result.returncode == 0

        reader = csv.DictReader(StringIO(result.stdout))
        fieldnames = reader.fieldnames or []

        assert "title" in fieldnames
        assert "year" in fieldnames
        assert "authors" in fieldnames


class TestCliSearchBibtexOutput:
    def test_bibtex_has_entries(self):
        result = run_cli(
            "search",
            "TITLE(transformer)",
            "--provider",
            "arxiv",
            "--max",
            "3",
            "--format",
            "bibtex",
        )
        assert result.returncode == 0

        entries = re.findall(r"@\w+\{", result.stdout)
        assert len(entries) >= 1

    def test_bibtex_entries_have_required_fields(self):
        result = run_cli(
            "search",
            "TITLE(neural network)",
            "--provider",
            "openalex",
            "--max",
            "3",
            "--format",
            "bibtex",
        )
        assert result.returncode == 0

        assert "title" in result.stdout.lower()
        assert "author" in result.stdout.lower()
        assert "year" in result.stdout.lower()


class TestCliSearchRisOutput:
    def test_ris_has_records(self):
        result = run_cli(
            "search",
            "TITLE(transformer)",
            "--provider",
            "arxiv",
            "--max",
            "3",
            "--format",
            "ris",
        )
        assert result.returncode == 0

        ty_count = result.stdout.count("TY  - ")
        er_count = result.stdout.count("ER  - ")

        assert ty_count >= 1
        assert ty_count == er_count

    def test_ris_has_required_tags(self):
        result = run_cli(
            "search",
            "TITLE(neural network)",
            "--provider",
            "openalex",
            "--max",
            "3",
            "--format",
            "ris",
        )
        assert result.returncode == 0

        assert "TI  - " in result.stdout
        assert "AU  - " in result.stdout


class TestCliSearchFileOutput:
    def test_output_to_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = Path(tmpdir) / "results.json"

            result = run_cli(
                "search",
                "TITLE(transformer)",
                "--provider",
                "arxiv",
                "--max",
                "3",
                "--format",
                "json",
                "--output",
                str(outfile),
            )
            assert result.returncode == 0
            assert outfile.exists()

            data = json.loads(outfile.read_text())
            assert len(data) >= 1

    def test_output_to_csv_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = Path(tmpdir) / "results.csv"

            result = run_cli(
                "search",
                "TITLE(neural network)",
                "--provider",
                "openalex",
                "--max",
                "3",
                "--format",
                "csv",
                "--output",
                str(outfile),
            )
            assert result.returncode == 0
            assert outfile.exists()

            with open(outfile) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) >= 1


class TestCliSearchMultipleProviders:
    def test_multiple_providers(self):
        result = run_cli(
            "search",
            "TITLE(transformer)",
            "--provider",
            "arxiv",
            "--provider",
            "openalex",
            "--max",
            "5",
        )
        assert result.returncode == 0

        papers = parse_json_output(result.stdout)
        assert len(papers) >= 1


class TestCliGet:
    def test_get_by_doi(self):
        result = run_cli("get", ATTENTION_PAPER_DOI, "--format", "json")
        assert result.returncode == 0

        data = json.loads(result.stdout)
        papers = data.get("papers", [data])
        assert len(papers) == 1
        assert "attention" in papers[0]["title"].lower()

    def test_get_by_doi_has_year(self):
        result = run_cli("get", ATTENTION_PAPER_DOI, "--format", "json")
        assert result.returncode == 0

        data = json.loads(result.stdout)
        papers = data.get("papers", [data])
        assert papers[0]["year"] is not None

    def test_get_invalid_doi(self):
        result = run_cli("get", "10.invalid/nonexistent")
        assert result.returncode != 0


class TestCliCitations:
    def test_citations_in(self):
        result = run_cli(
            "citations",
            ATTENTION_PAPER_DOI,
            "--direction",
            "in",
            "--max",
            "5",
            "--format",
            "json",
        )
        assert result.returncode == 0

        data = json.loads(result.stdout)
        papers = data.get("papers", data if isinstance(data, list) else [])
        assert len(papers) >= 1

        for paper in papers:
            year = paper.get("year")
            if year:
                assert year >= ATTENTION_PAPER_YEAR

    def test_citations_out(self):
        result = run_cli(
            "citations",
            ATTENTION_PAPER_DOI,
            "--direction",
            "out",
            "--max",
            "5",
            "--format",
            "json",
        )
        assert result.returncode == 0

        data = json.loads(result.stdout)
        papers = data.get("papers", data if isinstance(data, list) else [])
        assert len(papers) >= 1

        for paper in papers:
            year = paper.get("year")
            if year:
                assert year <= ATTENTION_PAPER_YEAR

    def test_citations_returns_success(self):
        result = run_cli(
            "citations",
            ATTENTION_PAPER_DOI,
            "--direction",
            "in",
            "--max",
            "3",
        )
        assert result.returncode == 0


class TestCliErrors:
    def test_invalid_query_syntax(self):
        result = run_cli("search", "TITLE((broken")
        assert result.returncode != 0

    def test_unknown_provider(self):
        result = run_cli("search", "TITLE(test)", "--provider", "notreal")
        assert result.returncode != 0

    def test_missing_query(self):
        result = run_cli("search")
        assert result.returncode != 0


class TestCliHelp:
    def test_main_help(self):
        result = run_cli("--help")
        assert result.returncode == 0
        assert "search" in result.stdout
        assert "get" in result.stdout
        assert "citations" in result.stdout

    def test_search_help(self):
        result = run_cli("search", "--help")
        assert result.returncode == 0
        assert "--provider" in result.stdout
        assert "--format" in result.stdout
        assert "--max" in result.stdout

    def test_get_help(self):
        result = run_cli("get", "--help")
        assert result.returncode == 0

    def test_citations_help(self):
        result = run_cli("citations", "--help")
        assert result.returncode == 0
        assert "--direction" in result.stdout
