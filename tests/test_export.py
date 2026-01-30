# tests/test_export.py
import json

import pytest

from scimesh.export import (
    BibtexExporter,
    CsvExporter,
    JsonExporter,
    RisExporter,
    TreeExporter,
    get_exporter,
)
from scimesh.models import Author, Paper, SearchResult


@pytest.fixture
def sample_result():
    papers = [
        Paper(
            title="Attention Is All You Need",
            authors=(Author(name="Ashish Vaswani"), Author(name="Noam Shazeer")),
            year=2017,
            source="arxiv",
            doi="10.48550/arXiv.1706.03762",
            abstract="We propose a new simple network architecture.",
            journal="NeurIPS",
        ),
        Paper(
            title="BERT: Pre-training of Deep Bidirectional Transformers",
            authors=(Author(name="Jacob Devlin"),),
            year=2019,
            source="scopus",
            doi="10.18653/v1/N19-1423",
        ),
    ]
    return SearchResult(papers=papers, total_by_provider={"arxiv": 1, "scopus": 1})


def test_get_exporter_csv():
    exporter = get_exporter("csv")
    assert isinstance(exporter, CsvExporter)


def test_get_exporter_json():
    exporter = get_exporter("json")
    assert isinstance(exporter, JsonExporter)


def test_get_exporter_bibtex():
    exporter = get_exporter("bibtex")
    assert isinstance(exporter, BibtexExporter)


def test_get_exporter_bib():
    exporter = get_exporter("bib")
    assert isinstance(exporter, BibtexExporter)


def test_get_exporter_ris():
    exporter = get_exporter("ris")
    assert isinstance(exporter, RisExporter)


def test_csv_export(sample_result):
    exporter = CsvExporter()
    output = exporter.to_string(sample_result)
    assert "Attention Is All You Need" in output
    assert "Ashish Vaswani; Noam Shazeer" in output
    assert "2017" in output


def test_json_export(sample_result):
    exporter = JsonExporter()
    output = exporter.to_string(sample_result)
    data = json.loads(output)
    assert len(data["papers"]) == 2
    assert data["total"] == 2
    assert data["papers"][0]["title"] == "Attention Is All You Need"


def test_bibtex_export(sample_result):
    exporter = BibtexExporter()
    output = exporter.to_string(sample_result)
    assert "@article{" in output
    assert "title = {Attention Is All You Need}" in output
    assert "author = {Ashish Vaswani and Noam Shazeer}" in output
    assert "year = {2017}" in output


def test_ris_export(sample_result):
    exporter = RisExporter()
    output = exporter.to_string(sample_result)
    assert "TY  - JOUR" in output
    assert "TI  - Attention Is All You Need" in output
    assert "AU  - Ashish Vaswani" in output
    assert "PY  - 2017" in output


def test_export_to_file(sample_result, tmp_path):
    exporter = CsvExporter()
    path = tmp_path / "output.csv"
    exporter.export(sample_result, path)
    assert path.exists()
    content = path.read_text()
    assert "Attention Is All You Need" in content


def test_get_exporter_tree():
    exporter = get_exporter("tree")
    assert isinstance(exporter, TreeExporter)


def test_tree_export(sample_result):
    exporter = TreeExporter()
    output = exporter.to_string(sample_result)
    # Paper titles as roots
    assert "Attention Is All You Need" in output
    assert "BERT" in output
    # Year as child
    assert "Year: 2017" in output
    assert "Year: 2019" in output
    # Authors present
    assert "Ashish Vaswani" in output
    # URL fallback to DOI
    assert "doi.org" in output


def test_tree_format_paper():
    paper = Paper(
        title="Test Paper",
        authors=(Author("Alice"), Author("Bob")),
        year=2020,
        source="test",
        url="https://example.com/paper",
    )
    exporter = TreeExporter()
    output = exporter.format_paper(paper)
    assert "Test Paper" in output
    assert "Year: 2020" in output
    assert "Authors: Alice, Bob" in output
    assert "URL: https://example.com/paper" in output


def test_tree_export_truncates_authors():
    papers = [
        Paper(
            title="Many Authors",
            authors=(Author("A"), Author("B"), Author("C"), Author("D"), Author("E")),
            year=2020,
            source="test",
        ),
    ]
    result = SearchResult(papers=papers)
    exporter = TreeExporter()
    output = exporter.to_string(result)
    assert "+2" in output  # 5 authors, show 3, truncate 2


def test_tree_export_empty_result():
    result = SearchResult(papers=[])
    exporter = TreeExporter()
    output = exporter.to_string(result)
    assert output == "No papers found."


def test_get_exporter_vault_raises():
    """Vault has a different interface, must be imported directly."""
    import pytest

    with pytest.raises(ValueError, match="Unknown export format: vault"):
        get_exporter("vault")


def test_vault_exporter_direct_import():
    """VaultExporter should be imported directly."""
    from scimesh.export.vault import VaultExporter

    exporter = VaultExporter()
    assert isinstance(exporter, VaultExporter)
