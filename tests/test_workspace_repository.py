"""Tests for YAML workspace repository."""

from datetime import datetime

import pytest

from scimesh.workspace.models import (
    CollectionWorkspace,
    Constraints,
    ExplorationWorkspace,
    Framework,
    LogEntry,
    PaperEntry,
    PaperIndex,
    Screening,
    SearchResults,
    SLRWorkspace,
    Stats,
)
from scimesh.workspace.repository import (
    WorkspaceNotFoundError,
    YamlWorkspaceRepository,
)


class TestYamlWorkspaceRepositoryPaths:
    """Tests for repository path properties."""

    def test_index_path(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        assert repo._index_path == tmp_path / "index.yaml"

    def test_log_path(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        assert repo._log_path == tmp_path / "log.yaml"

    def test_papers_path(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        assert repo._papers_path == tmp_path / "papers.yaml"


class TestYamlWorkspaceRepositoryExists:
    """Tests for exists method."""

    def test_exists_returns_false_when_no_index(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        assert repo.exists() is False

    def test_exists_returns_true_when_index_exists(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        (tmp_path / "index.yaml").write_text("type: collection\nquestion: test\n")
        assert repo.exists() is True


class TestYamlWorkspaceRepositorySaveLoadWorkspace:
    """Tests for save and load workspace methods."""

    def test_save_and_load_slr_workspace(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        workspace = SLRWorkspace(
            question="Does exercise help?",
            framework=Framework(type="pico", fields={"population": "adults"}),
            constraints=Constraints(databases=["openalex"], year_range="2020-2024"),
            stats=Stats(total=100, included=50),
            inclusion=["RCT"],
            exclusion=["case studies"],
        )
        repo.save(workspace)
        loaded = repo.load()
        assert isinstance(loaded, SLRWorkspace)
        assert loaded.type == "slr"
        assert loaded.question == "Does exercise help?"
        assert loaded.framework.type == "pico"
        assert loaded.framework.fields["population"] == "adults"
        assert loaded.constraints.databases == ["openalex"]
        assert loaded.constraints.year_range == "2020-2024"
        assert loaded.stats.total == 100
        assert loaded.inclusion == ["RCT"]
        assert loaded.exclusion == ["case studies"]

    def test_save_and_load_exploration_workspace(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        now = datetime.now()
        workspace = ExplorationWorkspace(
            question="AI trends?",
            constraints=Constraints(year_range="2023-2024"),
            limit=500,
            started_at=now,
        )
        repo.save(workspace)
        loaded = repo.load()
        assert isinstance(loaded, ExplorationWorkspace)
        assert loaded.type == "exploration"
        assert loaded.question == "AI trends?"
        assert loaded.limit == 500
        assert loaded.started_at == now

    def test_save_and_load_collection_workspace(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        workspace = CollectionWorkspace(
            question="My reading list",
            stats=Stats(total=25, with_pdf=20),
        )
        repo.save(workspace)
        loaded = repo.load()
        assert isinstance(loaded, CollectionWorkspace)
        assert loaded.type == "collection"
        assert loaded.question == "My reading list"
        assert loaded.stats.total == 25
        assert loaded.stats.with_pdf == 20

    def test_load_raises_when_not_found(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        with pytest.raises(WorkspaceNotFoundError):
            repo.load()

    def test_save_creates_directory(self, tmp_path):
        nested = tmp_path / "nested" / "path"
        repo = YamlWorkspaceRepository(nested)
        workspace = CollectionWorkspace(question="Test")
        repo.save(workspace)
        assert nested.exists()
        assert (nested / "index.yaml").exists()


class TestYamlWorkspaceRepositoryLog:
    """Tests for log methods."""

    def test_save_and_load_log(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        now = datetime.now()
        entries = [
            LogEntry(
                id="search-001",
                type="search",
                query="machine learning",
                providers=["openalex"],
                executed_at=now,
                results=SearchResults(total=100, unique=80),
            ),
            LogEntry(
                id="snowball-001",
                type="snowball",
                providers=["semantic_scholar"],
                executed_at=now,
                seed_doi="10.1234/test",
                direction="backward",
            ),
        ]
        repo.save_log(entries)
        loaded = repo.load_log()
        assert len(loaded) == 2
        assert loaded[0].id == "search-001"
        assert loaded[0].type == "search"
        assert loaded[0].query == "machine learning"
        assert loaded[0].results.total == 100
        assert loaded[1].id == "snowball-001"
        assert loaded[1].seed_doi == "10.1234/test"

    def test_load_log_returns_empty_when_not_found(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        loaded = repo.load_log()
        assert loaded == []

    def test_append_log_creates_file(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        now = datetime.now()
        entry = LogEntry(
            id="search-001",
            type="search",
            executed_at=now,
        )
        repo.append_log(entry)
        loaded = repo.load_log()
        assert len(loaded) == 1
        assert loaded[0].id == "search-001"

    def test_append_log_adds_to_existing(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        now = datetime.now()
        entry1 = LogEntry(id="search-001", type="search", executed_at=now)
        entry2 = LogEntry(id="search-002", type="search", executed_at=now)
        repo.append_log(entry1)
        repo.append_log(entry2)
        loaded = repo.load_log()
        assert len(loaded) == 2
        assert loaded[0].id == "search-001"
        assert loaded[1].id == "search-002"


class TestYamlWorkspaceRepositoryPapers:
    """Tests for papers index methods."""

    def test_save_and_load_papers(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        papers = [
            PaperEntry(
                path="papers/2024/smith-ml",
                doi="10.1234/test1",
                title="Machine Learning Survey",
                status="included",
                search_ids=["search-001"],
            ),
            PaperEntry(
                path="papers/2023/jones-ai",
                doi="10.1234/test2",
                title="AI Review",
                status="excluded",
                search_ids=["search-002"],
            ),
        ]
        repo.save_papers(papers)
        loaded = repo.load_papers()
        assert len(loaded) == 2
        assert loaded[0].path == "papers/2024/smith-ml"
        assert loaded[0].doi == "10.1234/test1"
        assert loaded[0].status == "included"
        assert loaded[1].path == "papers/2023/jones-ai"
        assert loaded[1].title == "AI Review"

    def test_load_papers_returns_empty_when_not_found(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        loaded = repo.load_papers()
        assert loaded == []


class TestYamlWorkspaceRepositoryPaper:
    """Tests for individual paper methods."""

    def test_save_and_load_paper(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        now = datetime.now()
        paper = PaperIndex(
            title="Attention Is All You Need",
            authors=["Vaswani", "Shazeer"],
            year=2017,
            doi="10.48550/arXiv.1706.03762",
            sources=["openalex", "semantic_scholar"],
            urls={"doi": "https://doi.org/10.48550/arXiv.1706.03762"},
            tags=["transformers", "nlp"],
            citations=50000,
            journal="NeurIPS",
            open_access=True,
            pdf="attention.pdf",
            abstract="The dominant sequence transduction models...",
            screening=Screening(status="included", reason="Seminal paper", screened_at=now),
        )
        path = "papers/2017/vaswani-attention"
        repo.save_paper(path, paper)
        loaded = repo.load_paper(path)
        assert loaded.title == "Attention Is All You Need"
        assert loaded.authors == ["Vaswani", "Shazeer"]
        assert loaded.year == 2017
        assert loaded.doi == "10.48550/arXiv.1706.03762"
        assert loaded.tags == ["transformers", "nlp"]
        assert loaded.citations == 50000
        assert loaded.screening.status == "included"

    def test_save_paper_creates_directory_structure(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        paper = PaperIndex(
            title="Test Paper",
            authors=["Author"],
            year=2024,
        )
        path = "papers/2024/author-test"
        repo.save_paper(path, paper)
        expected_file = tmp_path / "papers" / "2024" / "author-test" / "index.yaml"
        assert expected_file.exists()

    def test_load_paper_raises_when_not_found(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        with pytest.raises(FileNotFoundError):
            repo.load_paper("papers/2024/nonexistent")

    def test_paper_exists_returns_false_when_not_found(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        assert repo.paper_exists("papers/2024/nonexistent") is False

    def test_paper_exists_returns_true_when_found(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        paper = PaperIndex(
            title="Test Paper",
            authors=["Author"],
            year=2024,
        )
        path = "papers/2024/author-test"
        repo.save_paper(path, paper)
        assert repo.paper_exists(path) is True


class TestYamlWorkspaceRepositoryRoundtrip:
    """Tests for full roundtrip serialization."""

    def test_full_workspace_roundtrip(self, tmp_path):
        repo = YamlWorkspaceRepository(tmp_path)
        now = datetime.now()
        workspace = SLRWorkspace(
            question="Does X affect Y?",
            framework=Framework(type="pico", fields={"population": "adults"}),
            constraints=Constraints(databases=["openalex"], year_range="2020-2024"),
            stats=Stats(total=2, included=1, excluded=1),
            inclusion=["RCT"],
            exclusion=["case study"],
        )
        repo.save(workspace)
        log_entries = [
            LogEntry(
                id="search-001",
                type="search",
                query="X AND Y",
                providers=["openalex"],
                executed_at=now,
                results=SearchResults(total=100, unique=50),
            ),
        ]
        repo.save_log(log_entries)
        papers = [
            PaperEntry(
                path="papers/2024/smith-xy",
                doi="10.1234/xy1",
                title="X affects Y",
                status="included",
                search_ids=["search-001"],
            ),
            PaperEntry(
                path="papers/2023/jones-xy",
                doi="10.1234/xy2",
                title="X does not affect Y",
                status="excluded",
                search_ids=["search-001"],
            ),
        ]
        repo.save_papers(papers)
        paper1 = PaperIndex(
            title="X affects Y",
            authors=["Smith"],
            year=2024,
            doi="10.1234/xy1",
            screening=Screening(status="included", reason="RCT", screened_at=now),
        )
        paper2 = PaperIndex(
            title="X does not affect Y",
            authors=["Jones"],
            year=2023,
            doi="10.1234/xy2",
            screening=Screening(status="excluded", reason="Case study", screened_at=now),
        )
        repo.save_paper("papers/2024/smith-xy", paper1)
        repo.save_paper("papers/2023/jones-xy", paper2)
        loaded_workspace = repo.load()
        assert isinstance(loaded_workspace, SLRWorkspace)
        assert loaded_workspace.question == "Does X affect Y?"
        loaded_log = repo.load_log()
        assert len(loaded_log) == 1
        assert loaded_log[0].query == "X AND Y"
        loaded_papers = repo.load_papers()
        assert len(loaded_papers) == 2
        loaded_paper1 = repo.load_paper("papers/2024/smith-xy")
        assert loaded_paper1.title == "X affects Y"
        assert loaded_paper1.screening.status == "included"
        loaded_paper2 = repo.load_paper("papers/2023/jones-xy")
        assert loaded_paper2.title == "X does not affect Y"
        assert loaded_paper2.screening.status == "excluded"
