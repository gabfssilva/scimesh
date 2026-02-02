from __future__ import annotations

import csv
import json
import re
import tempfile
from io import StringIO
from pathlib import Path

import pytest

from scimesh import collect_search, search
from scimesh.export import get_exporter
from scimesh.providers import Arxiv, OpenAlex
from scimesh.query import author, title, year


class TestExportJson:
    @pytest.mark.asyncio
    async def test_json_is_valid(self):
        q = title("transformer")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("json")
        output = exporter.to_string(result)

        data = json.loads(output)
        assert isinstance(data, list) or "papers" in data

    @pytest.mark.asyncio
    async def test_json_has_required_fields(self):
        q = title("neural network")
        result = await collect_search(search(q, providers=[OpenAlex()], take=10))

        exporter = get_exporter("json")
        output = exporter.to_string(result)
        data = json.loads(output)

        papers = data.get("papers", data) if isinstance(data, dict) else data
        assert len(papers) >= 1
        paper = papers[0]

        required_fields = ["title", "authors", "year"]
        for field in required_fields:
            assert field in paper, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_json_preserves_query_data(self):
        q = title("self-attention") & author("Vaswani") & year(2017, 2020)
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("json")
        output = exporter.to_string(result)
        data = json.loads(output)

        papers = data.get("papers", data) if isinstance(data, dict) else data
        for paper_data in papers:
            assert "attention" in paper_data["title"].lower()
            author_names = " ".join(
                a["name"] if isinstance(a, dict) else str(a) for a in paper_data["authors"]
            ).lower()
            assert "vaswani" in author_names
            assert 2017 <= paper_data["year"] <= 2020

    @pytest.mark.asyncio
    async def test_json_to_file(self):
        q = title("deep learning")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "papers.json"
            exporter = get_exporter("json")
            exporter.export(result, filepath)

            assert filepath.exists()
            data = json.loads(filepath.read_text())
            assert len(data) >= 1


class TestExportCsv:
    @pytest.mark.asyncio
    async def test_csv_is_valid(self):
        q = title("transformer")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("csv")
        output = exporter.to_string(result)

        reader = csv.DictReader(StringIO(output))
        rows = list(reader)

        assert len(rows) >= 1

    @pytest.mark.asyncio
    async def test_csv_has_required_columns(self):
        q = title("neural network")
        result = await collect_search(search(q, providers=[OpenAlex()], take=10))

        exporter = get_exporter("csv")
        output = exporter.to_string(result)

        reader = csv.DictReader(StringIO(output))
        fieldnames = reader.fieldnames or []

        required_columns = ["title", "year", "authors"]
        for col in required_columns:
            assert col in fieldnames, f"Missing column: {col}"

    @pytest.mark.asyncio
    async def test_csv_data_matches_query(self):
        q = title("self-attention") & year(2017, 2020)
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("csv")
        output = exporter.to_string(result)

        reader = csv.DictReader(StringIO(output))
        for row in reader:
            assert "attent" in row["title"].lower()
            year_val = int(row["year"])
            assert 2017 <= year_val <= 2020

    @pytest.mark.asyncio
    async def test_csv_to_file(self):
        q = title("machine learning")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "papers.csv"
            exporter = get_exporter("csv")
            exporter.export(result, filepath)

            assert filepath.exists()

            with open(filepath) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) >= 1


class TestExportBibtex:
    @pytest.mark.asyncio
    async def test_bibtex_has_entries(self):
        q = title("transformer")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("bibtex")
        output = exporter.to_string(result)

        entry_pattern = r"@\w+\{"
        entries = re.findall(entry_pattern, output)
        assert len(entries) >= 1

    @pytest.mark.asyncio
    async def test_bibtex_has_required_fields(self):
        q = title("neural network")
        result = await collect_search(search(q, providers=[OpenAlex()], take=10))

        exporter = get_exporter("bibtex")
        output = exporter.to_string(result)

        assert "title" in output.lower()
        assert "author" in output.lower()
        assert "year" in output.lower()

    @pytest.mark.asyncio
    async def test_bibtex_entry_structure(self):
        q = title("self-attention") & author("Vaswani")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("bibtex")
        output = exporter.to_string(result)

        entry_match = re.search(r"@(\w+)\{([^,]+),", output)
        assert entry_match is not None, "No BibTeX entry found"

        entry_type = entry_match.group(1)
        assert entry_type in ("article", "misc", "inproceedings", "book", "techreport")

    @pytest.mark.asyncio
    async def test_bibtex_contains_query_data(self):
        q = title("deep learning") & year(2020, 2022)
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("bibtex")
        output = exporter.to_string(result)

        assert "deep learning" in output.lower() or "Deep Learning" in output
        assert "2020" in output or "2021" in output or "2022" in output

    @pytest.mark.asyncio
    async def test_bibtex_to_file(self):
        q = title("machine learning")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "papers.bib"
            exporter = get_exporter("bibtex")
            exporter.export(result, filepath)

            assert filepath.exists()
            content = filepath.read_text()
            assert "@" in content


class TestExportRis:
    @pytest.mark.asyncio
    async def test_ris_has_records(self):
        q = title("transformer")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("ris")
        output = exporter.to_string(result)

        assert output.count("TY  - ") >= 1
        assert output.count("ER  - ") >= 1

    @pytest.mark.asyncio
    async def test_ris_records_are_balanced(self):
        q = title("neural network")
        result = await collect_search(search(q, providers=[OpenAlex()], take=10))

        exporter = get_exporter("ris")
        output = exporter.to_string(result)

        ty_count = output.count("TY  - ")
        er_count = output.count("ER  - ")

        assert ty_count == er_count, f"Unbalanced RIS: {ty_count} TY vs {er_count} ER"

    @pytest.mark.asyncio
    async def test_ris_has_required_tags(self):
        q = title("self-attention")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("ris")
        output = exporter.to_string(result)

        assert "TI  - " in output, "Missing title tag"
        assert "PY  - " in output or "Y1  - " in output, "Missing year tag"
        assert "AU  - " in output, "Missing author tag"

    @pytest.mark.asyncio
    async def test_ris_contains_query_data(self):
        q = title("deep learning")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("ris")
        output = exporter.to_string(result)

        title_match = re.search(r"TI  - (.+)", output)
        assert title_match is not None
        assert (
            "deep learning" in title_match.group(1).lower()
            or "learning" in title_match.group(1).lower()
        )

    @pytest.mark.asyncio
    async def test_ris_to_file(self):
        q = title("machine learning")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "papers.ris"
            exporter = get_exporter("ris")
            exporter.export(result, filepath)

            assert filepath.exists()
            content = filepath.read_text()
            assert "TY  - " in content


class TestExportTree:
    @pytest.mark.asyncio
    async def test_tree_has_papers(self):
        q = title("transformer")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("tree")
        output = exporter.to_string(result)

        assert len(output) > 0
        assert "├──" in output or "└──" in output

    @pytest.mark.asyncio
    async def test_tree_shows_year(self):
        q = title("self-attention") & year(2017, 2020)
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("tree")
        output = exporter.to_string(result)

        assert "Year:" in output

    @pytest.mark.asyncio
    async def test_tree_shows_authors(self):
        q = title("neural network")
        result = await collect_search(search(q, providers=[OpenAlex()], take=10))

        exporter = get_exporter("tree")
        output = exporter.to_string(result)

        assert "Authors:" in output

    @pytest.mark.asyncio
    async def test_tree_shows_url(self):
        q = title("deep learning")
        result = await collect_search(search(q, providers=[Arxiv()], take=10))

        exporter = get_exporter("tree")
        output = exporter.to_string(result)

        assert "URL:" in output or "http" in output
