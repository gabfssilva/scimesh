# tests/test_vault_export.py
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from scimesh.export.vault import generate_folder_name
from scimesh.models import Author, Paper


def test_generate_folder_name_basic():
    paper = Paper(
        title="Attention Is All You Need",
        authors=(Author(name="Ashish Vaswani"), Author(name="Noam Shazeer")),
        year=2017,
        source="arxiv",
    )
    result = generate_folder_name(paper)
    assert result == "2017-vaswani-attention-is-all-you-need"


def test_generate_folder_name_single_author():
    paper = Paper(
        title="BERT: Pre-training of Deep Bidirectional Transformers",
        authors=(Author(name="Jacob Devlin"),),
        year=2019,
        source="scopus",
    )
    result = generate_folder_name(paper)
    assert result == "2019-devlin-bert-pre-training-of-deep-bidirectional"


def test_generate_folder_name_special_chars():
    paper = Paper(
        title="What's in a Name? The Impact of AI/ML on Society",
        authors=(Author(name="Jane O'Connor"),),
        year=2023,
        source="openalex",
    )
    result = generate_folder_name(paper)
    # Special chars removed, lowercase, hyphenated
    assert result == "2023-oconnor-whats-in-a-name-the-impact"


def test_generate_folder_name_short_title():
    paper = Paper(
        title="GPT-4",
        authors=(Author(name="OpenAI Team"),),
        year=2023,
        source="arxiv",
    )
    result = generate_folder_name(paper)
    assert result == "2023-team-gpt-4"


def test_generate_folder_name_no_authors():
    paper = Paper(
        title="Anonymous Research Paper",
        authors=(),
        year=2020,
        source="arxiv",
    )
    result = generate_folder_name(paper)
    assert result == "2020-unknown-anonymous-research-paper"


def test_build_paper_index_full():
    from scimesh.export.vault import build_paper_index

    paper = Paper(
        title="Attention Is All You Need",
        authors=(Author(name="Ashish Vaswani"), Author(name="Noam Shazeer")),
        year=2017,
        source="arxiv",
        doi="10.5555/3295222.3295349",
        abstract="We propose a new simple network architecture.",
        topics=("transformer", "attention"),
        citations_count=98245,
        journal="NeurIPS",
        open_access=True,
        url="https://arxiv.org/abs/1706.03762",
    )

    result = build_paper_index(paper, pdf_filename="fulltext.pdf")
    data = yaml.safe_load(result)

    assert data["title"] == "Attention Is All You Need"
    assert data["authors"] == ["Ashish Vaswani", "Noam Shazeer"]
    assert data["year"] == 2017
    assert data["doi"] == "10.5555/3295222.3295349"
    assert data["sources"] == ["arxiv"]
    assert data["urls"] == {"arxiv": "https://arxiv.org/abs/1706.03762"}
    assert data["tags"] == ["attention", "transformer"]
    assert data["citations"] == 98245
    assert data["journal"] == "NeurIPS"
    assert data["open_access"] is True
    assert data["pdf"] == "fulltext.pdf"
    assert data["abstract"] == "We propose a new simple network architecture."


def test_build_paper_index_minimal():
    from scimesh.export.vault import build_paper_index

    paper = Paper(
        title="Minimal Paper",
        authors=(Author(name="Test Author"),),
        year=2020,
        source="openalex",
    )

    result = build_paper_index(paper, pdf_filename=None)
    data = yaml.safe_load(result)

    assert data["title"] == "Minimal Paper"
    assert data["authors"] == ["Test Author"]
    assert data["year"] == 2020
    assert "pdf" not in data
    assert "abstract" not in data
    assert "doi" not in data


def test_build_paper_index_merged_sources():
    """Test paper that came from multiple sources after dedup."""
    from scimesh.export.vault import build_paper_index

    paper = Paper(
        title="Multi-source Paper",
        authors=(Author(name="Author One"),),
        year=2021,
        source="openalex",  # Primary source
        url="https://openalex.org/W123",
        extras={
            "arxiv_url": "https://arxiv.org/abs/2101.00001",
            "scopus_url": "https://scopus.com/record/123",
        },
    )

    result = build_paper_index(
        paper,
        pdf_filename=None,
        additional_sources=["arxiv", "scopus"],
    )
    data = yaml.safe_load(result)

    assert set(data["sources"]) == {"openalex", "arxiv", "scopus"}


def test_build_root_index_new():
    from scimesh.export.vault import VaultStats, build_root_index

    stats = VaultStats(
        total=42,
        by_provider={"openalex": 38, "arxiv": 12},
        with_pdf=28,
        deduplicated=8,
        skipped=0,
    )

    papers_list = [
        {
            "path": "2017-vaswani-attention-is-all",
            "doi": "10.5555/123",
            "title": "Attention Is All You Need",
        },
        {"path": "2020-brown-language-models", "doi": "10.5555/456", "title": "Language Models"},
    ]

    result = build_root_index(
        query="TITLE(attention)",
        providers=["openalex", "arxiv"],
        stats=stats,
        papers=papers_list,
        existing_data=None,
    )

    data = yaml.safe_load(result)

    assert data["query"] == "TITLE(attention)"
    assert data["providers"] == ["openalex", "arxiv"]
    assert "searched_at" in data
    assert data["stats"]["total"] == 42
    assert data["stats"]["with_pdf"] == 28
    assert len(data["papers"]) == 2


def test_build_root_index_update_existing():
    from scimesh.export.vault import VaultStats, build_root_index

    existing = {
        "query": "TITLE(attention)",
        "providers": ["openalex"],
        "searched_at": "2026-01-01T10:00:00Z",
        "stats": {
            "total": 10,
            "by_provider": {"openalex": 10},
            "with_pdf": 5,
            "deduplicated": 0,
            "skipped": 0,
        },
        "papers": [
            {"path": "2017-vaswani-attention-is-all", "doi": "10.5555/123", "title": "Paper 1"},
        ],
    }

    new_stats = VaultStats(
        total=5,
        by_provider={"arxiv": 5},
        with_pdf=3,
        deduplicated=0,
        skipped=1,  # One was already in existing
    )

    new_papers = [
        {"path": "2020-brown-language-models", "doi": "10.5555/456", "title": "Paper 2"},
    ]

    result = build_root_index(
        query="TITLE(transformer)",
        providers=["arxiv"],
        stats=new_stats,
        papers=new_papers,
        existing_data=existing,
    )

    data = yaml.safe_load(result)

    # Original searched_at preserved
    assert data["searched_at"] == "2026-01-01T10:00:00Z"
    # Updated_at added
    assert "updated_at" in data
    # Stats merged
    assert data["stats"]["total"] == 15  # 10 + 5
    assert data["stats"]["by_provider"]["openalex"] == 10
    assert data["stats"]["by_provider"]["arxiv"] == 5
    # Papers merged (no duplicates by path)
    assert len(data["papers"]) == 2
    paths = [p["path"] for p in data["papers"]]
    assert "2017-vaswani-attention-is-all" in paths
    assert "2020-brown-language-models" in paths


def test_vault_exporter_creates_structure(tmp_path):
    from scimesh.export.vault import VaultExporter
    from scimesh.models import SearchResult

    papers = [
        Paper(
            title="Attention Is All You Need",
            authors=(Author(name="Ashish Vaswani"),),
            year=2017,
            source="arxiv",
            doi="10.5555/123",
            abstract="A paper about attention.",
        ),
        Paper(
            title="BERT Paper",
            authors=(Author(name="Jacob Devlin"),),
            year=2019,
            source="openalex",
        ),
    ]

    result = SearchResult(papers=papers, total_by_provider={"arxiv": 1, "openalex": 1})
    output_dir = tmp_path / "vault"

    exporter = VaultExporter()
    stats = exporter.export(
        result=result,
        output_dir=output_dir,
    )

    # Check structure created
    assert output_dir.exists()

    # Check paper folders
    paper1_dir = output_dir / "2017-vaswani-attention-is-all-you-need"
    paper2_dir = output_dir / "2019-devlin-bert-paper"

    assert paper1_dir.exists()
    assert (paper1_dir / "index.yaml").exists()
    assert paper2_dir.exists()
    assert (paper2_dir / "index.yaml").exists()

    # Check stats
    assert stats.total == 2
    assert stats.skipped == 0


def test_vault_exporter_skips_existing(tmp_path):
    from scimesh.export.vault import VaultExporter
    from scimesh.models import SearchResult

    output_dir = tmp_path / "vault"

    # Create existing paper folder and papers.yaml
    existing_folder = output_dir / "2017-vaswani-attention-is-all-you-need"
    existing_folder.mkdir(parents=True)
    (existing_folder / "index.yaml").write_text("title: Existing\n")
    # Create papers.yaml with the existing paper
    (output_dir / "papers.yaml").write_text(
        "- path: 2017-vaswani-attention-is-all-you-need\n"
        "  doi: ''\n"
        "  title: Existing\n"
        "  status: unscreened\n"
        "  search_ids: []\n"
    )

    papers = [
        Paper(
            title="Attention Is All You Need",
            authors=(Author(name="Ashish Vaswani"),),
            year=2017,
            source="arxiv",
        ),
    ]

    result = SearchResult(papers=papers)
    exporter = VaultExporter()
    stats = exporter.export(
        result=result,
        output_dir=output_dir,
    )

    # Should skip existing
    assert stats.skipped == 1
    assert stats.total == 0

    # Existing content preserved
    content = (existing_folder / "index.yaml").read_text()
    assert "Existing" in content


@pytest.mark.asyncio
async def test_vault_exporter_downloads_pdf(tmp_path: Path):
    from scimesh.export.vault import VaultExporter
    from scimesh.models import SearchResult

    papers = [
        Paper(
            title="Paper With PDF",
            authors=(Author(name="Author One"),),
            year=2020,
            source="openalex",
            doi="10.1234/test",
            pdf_url="https://example.com/paper.pdf",
            open_access=True,
        ),
    ]

    result = SearchResult(papers=papers)
    output_dir = tmp_path / "vault"

    # Mock downloader
    mock_downloader = MagicMock()
    mock_downloader.download = AsyncMock(return_value=b"%PDF-1.4 fake pdf content")

    exporter = VaultExporter(downloader=mock_downloader)
    stats = await exporter.export_async(
        result=result,
        output_dir=output_dir,
    )

    # Check PDF was downloaded
    paper_dir = output_dir / "2020-one-paper-with-pdf"
    assert (paper_dir / "fulltext.pdf").exists()

    # Check index.yaml references PDF
    index_content = yaml.safe_load((paper_dir / "index.yaml").read_text())
    assert index_content["pdf"] == "fulltext.pdf"

    assert stats.with_pdf == 1


@pytest.mark.asyncio
async def test_vault_exporter_handles_download_failure(tmp_path: Path):
    from scimesh.export.vault import VaultExporter
    from scimesh.models import SearchResult

    papers = [
        Paper(
            title="Paper Without PDF",
            authors=(Author(name="Author One"),),
            year=2020,
            source="openalex",
            doi="10.1234/test",
        ),
    ]

    result = SearchResult(papers=papers)
    output_dir = tmp_path / "vault"

    # Mock downloader that fails
    mock_downloader = MagicMock()
    mock_downloader.download = AsyncMock(return_value=None)

    exporter = VaultExporter(downloader=mock_downloader)
    stats = await exporter.export_async(
        result=result,
        output_dir=output_dir,
    )

    # Paper still exported, just without PDF
    paper_dir = output_dir / "2020-one-paper-without-pdf"
    assert paper_dir.exists()
    assert not (paper_dir / "fulltext.pdf").exists()

    # Check index.yaml has no pdf field
    index_content = yaml.safe_load((paper_dir / "index.yaml").read_text())
    assert "pdf" not in index_content

    assert stats.with_pdf == 0
    assert stats.total == 1
