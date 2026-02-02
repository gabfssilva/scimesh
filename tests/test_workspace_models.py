# tests/test_workspace_models.py
"""Tests for workspace models including Constraints, Stats, Workspace types, and Paper models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from scimesh.workspace.models import (
    CollectionWorkspace,
    Condensed,
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
    parse_workspace,
)


class TestConstraints:
    """Tests for Constraints model."""

    def test_default_values(self):
        constraints = Constraints()
        assert constraints.databases == ["openalex", "semantic_scholar"]
        assert constraints.year_range is None

    def test_custom_databases(self):
        constraints = Constraints(databases=["arxiv", "scopus"])
        assert constraints.databases == ["arxiv", "scopus"]

    def test_with_year_range(self):
        constraints = Constraints(year_range="2020-2024")
        assert constraints.year_range == "2020-2024"

    def test_from_dict(self):
        data = {"databases": ["arxiv"], "year_range": "2015-2020"}
        constraints = Constraints.model_validate(data)
        assert constraints.databases == ["arxiv"]
        assert constraints.year_range == "2015-2020"

    def test_to_dict(self):
        constraints = Constraints(databases=["openalex"], year_range="2020-2024")
        data = constraints.model_dump()
        assert data["databases"] == ["openalex"]
        assert data["year_range"] == "2020-2024"


class TestStats:
    """Tests for Stats model."""

    def test_default_values(self):
        stats = Stats()
        assert stats.total == 0
        assert stats.with_pdf == 0
        assert stats.included == 0
        assert stats.excluded == 0
        assert stats.maybe == 0
        assert stats.unscreened == 0

    def test_custom_values(self):
        stats = Stats(total=100, with_pdf=50, included=30, excluded=20, maybe=10, unscreened=40)
        assert stats.total == 100
        assert stats.with_pdf == 50
        assert stats.included == 30
        assert stats.excluded == 20
        assert stats.maybe == 10
        assert stats.unscreened == 40

    def test_from_dict(self):
        data = {"total": 50, "with_pdf": 25, "included": 10}
        stats = Stats.model_validate(data)
        assert stats.total == 50
        assert stats.with_pdf == 25
        assert stats.included == 10
        assert stats.excluded == 0  # Default

    def test_to_dict(self):
        stats = Stats(total=100, included=50)
        data = stats.model_dump()
        assert data["total"] == 100
        assert data["included"] == 50


class TestFramework:
    """Tests for Framework model."""

    def test_creation(self):
        fields = {"population": "elderly", "intervention": "exercise"}
        framework = Framework(type="pico", fields=fields)
        assert framework.type == "pico"
        assert framework.fields["population"] == "elderly"

    def test_default_fields(self):
        framework = Framework(type="custom")
        assert framework.fields == {}

    def test_from_dict(self):
        data = {"type": "spider", "fields": {"sample": "nurses"}}
        framework = Framework.model_validate(data)
        assert framework.type == "spider"
        assert framework.fields["sample"] == "nurses"


class TestSLRWorkspace:
    """Tests for SLRWorkspace model."""

    def test_creation(self):
        framework = Framework(type="pico", fields={"population": "patients"})
        workspace = SLRWorkspace(
            question="Does exercise help?",
            framework=framework,
            inclusion=["RCT"],
            exclusion=["case studies"],
        )
        assert workspace.type == "slr"
        assert workspace.question == "Does exercise help?"
        assert workspace.framework.type == "pico"
        assert workspace.inclusion == ["RCT"]
        assert workspace.exclusion == ["case studies"]

    def test_default_values(self):
        framework = Framework(type="pico")
        workspace = SLRWorkspace(question="Test?", framework=framework)
        assert workspace.type == "slr"
        assert workspace.constraints.databases == ["openalex", "semantic_scholar"]
        assert workspace.stats.total == 0
        assert workspace.inclusion == []
        assert workspace.exclusion == []

    def test_type_is_literal(self):
        framework = Framework(type="pico")
        workspace = SLRWorkspace(question="Test?", framework=framework)
        assert workspace.type == "slr"

    def test_from_dict(self):
        data = {
            "type": "slr",
            "question": "Research question?",
            "framework": {"type": "pico", "fields": {"population": "test"}},
            "constraints": {"databases": ["arxiv"]},
            "inclusion": ["peer-reviewed"],
            "exclusion": ["preprints"],
        }
        workspace = SLRWorkspace.model_validate(data)
        assert workspace.type == "slr"
        assert workspace.question == "Research question?"
        assert workspace.constraints.databases == ["arxiv"]


class TestExplorationWorkspace:
    """Tests for ExplorationWorkspace model."""

    def test_creation(self):
        workspace = ExplorationWorkspace(question="What are the trends?", limit=100)
        assert workspace.type == "exploration"
        assert workspace.question == "What are the trends?"
        assert workspace.limit == 100

    def test_default_values(self):
        workspace = ExplorationWorkspace(question="Test?")
        assert workspace.type == "exploration"
        assert workspace.limit is None
        assert workspace.started_at is None
        assert workspace.finished_at is None
        assert workspace.constraints.databases == ["openalex", "semantic_scholar"]
        assert workspace.stats.total == 0

    def test_with_timestamps(self):
        now = datetime.now()
        workspace = ExplorationWorkspace(question="Test?", started_at=now, finished_at=now)
        assert workspace.started_at == now
        assert workspace.finished_at == now

    def test_from_dict(self):
        data = {
            "type": "exploration",
            "question": "Trends in AI?",
            "limit": 500,
            "constraints": {"year_range": "2020-2024"},
        }
        workspace = ExplorationWorkspace.model_validate(data)
        assert workspace.type == "exploration"
        assert workspace.limit == 500
        assert workspace.constraints.year_range == "2020-2024"


class TestCollectionWorkspace:
    """Tests for CollectionWorkspace model."""

    def test_creation(self):
        workspace = CollectionWorkspace(question="My reading list")
        assert workspace.type == "collection"
        assert workspace.question == "My reading list"

    def test_default_values(self):
        workspace = CollectionWorkspace(question="Papers collection")
        assert workspace.type == "collection"
        assert workspace.constraints.databases == ["openalex", "semantic_scholar"]
        assert workspace.stats.total == 0

    def test_from_dict(self):
        data = {
            "type": "collection",
            "question": "ML papers 2024",
            "stats": {"total": 50, "with_pdf": 30},
        }
        workspace = CollectionWorkspace.model_validate(data)
        assert workspace.type == "collection"
        assert workspace.question == "ML papers 2024"
        assert workspace.stats.total == 50
        assert workspace.stats.with_pdf == 30


class TestParseWorkspace:
    """Tests for parse_workspace discriminated union function."""

    def test_parse_slr_workspace(self):
        data = {
            "type": "slr",
            "question": "SLR question",
            "framework": {"type": "pico", "fields": {}},
        }
        workspace = parse_workspace(data)
        assert isinstance(workspace, SLRWorkspace)
        assert workspace.type == "slr"
        assert workspace.question == "SLR question"

    def test_parse_exploration_workspace(self):
        data = {
            "type": "exploration",
            "question": "Exploration question",
            "limit": 200,
        }
        workspace = parse_workspace(data)
        assert isinstance(workspace, ExplorationWorkspace)
        assert workspace.type == "exploration"
        assert workspace.limit == 200

    def test_parse_collection_workspace(self):
        data = {
            "type": "collection",
            "question": "Collection question",
        }
        workspace = parse_workspace(data)
        assert isinstance(workspace, CollectionWorkspace)
        assert workspace.type == "collection"

    def test_parse_invalid_type(self):
        data = {
            "type": "invalid",
            "question": "Invalid workspace",
        }
        with pytest.raises(ValidationError):
            parse_workspace(data)

    def test_parse_missing_type(self):
        data = {"question": "No type specified"}
        with pytest.raises(ValidationError):
            parse_workspace(data)


class TestSearchResults:
    """Tests for SearchResults model."""

    def test_creation(self):
        results = SearchResults(total=100, unique=80)
        assert results.total == 100
        assert results.unique == 80

    def test_from_dict(self):
        data = {"total": 50, "unique": 45}
        results = SearchResults.model_validate(data)
        assert results.total == 50
        assert results.unique == 45


class TestCondensed:
    """Tests for Condensed model."""

    def test_creation_minimal(self):
        condensed = Condensed(
            problem="How to improve transformer efficiency",
            method="Sparse attention mechanisms",
            results="30% reduction in compute with minimal accuracy loss",
        )
        assert condensed.problem == "How to improve transformer efficiency"
        assert condensed.method == "Sparse attention mechanisms"
        assert condensed.results == "30% reduction in compute with minimal accuracy loss"
        assert condensed.limitations is None
        assert condensed.relevance_to_exploration is None

    def test_creation_full(self):
        condensed = Condensed(
            problem="Neural network interpretability",
            method="Attention visualization techniques",
            results="Improved understanding of model decisions",
            limitations="Only works for attention-based models",
            relevance_to_exploration="Directly addresses explainability research question",
        )
        assert condensed.problem == "Neural network interpretability"
        assert condensed.method == "Attention visualization techniques"
        assert condensed.results == "Improved understanding of model decisions"
        assert condensed.limitations == "Only works for attention-based models"
        assert (
            condensed.relevance_to_exploration
            == "Directly addresses explainability research question"
        )

    def test_from_dict(self):
        data = {
            "problem": "Data scarcity in NLP",
            "method": "Data augmentation",
            "results": "10% improvement on benchmarks",
            "limitations": "Language-specific techniques",
        }
        condensed = Condensed.model_validate(data)
        assert condensed.problem == "Data scarcity in NLP"
        assert condensed.method == "Data augmentation"
        assert condensed.results == "10% improvement on benchmarks"
        assert condensed.limitations == "Language-specific techniques"
        assert condensed.relevance_to_exploration is None

    def test_to_dict(self):
        condensed = Condensed(
            problem="Test problem",
            method="Test method",
            results="Test results",
            limitations="Test limitations",
        )
        data = condensed.model_dump()
        assert data["problem"] == "Test problem"
        assert data["method"] == "Test method"
        assert data["results"] == "Test results"
        assert data["limitations"] == "Test limitations"
        assert data["relevance_to_exploration"] is None

    def test_serialization_roundtrip(self):
        original = Condensed(
            problem="Original problem",
            method="Original method",
            results="Original results",
            limitations="Original limitations",
            relevance_to_exploration="High relevance",
        )
        data = original.model_dump()
        restored = Condensed.model_validate(data)
        assert restored.problem == original.problem
        assert restored.method == original.method
        assert restored.results == original.results
        assert restored.limitations == original.limitations
        assert restored.relevance_to_exploration == original.relevance_to_exploration


class TestLogEntry:
    """Tests for LogEntry model."""

    def test_creation_search(self):
        now = datetime.now()
        entry = LogEntry(
            id="search-001",
            type="search",
            query="machine learning",
            providers=["openalex", "semantic_scholar"],
            executed_at=now,
            results=SearchResults(total=100, unique=80),
        )
        assert entry.id == "search-001"
        assert entry.type == "search"
        assert entry.query == "machine learning"
        assert entry.providers == ["openalex", "semantic_scholar"]
        assert entry.executed_at == now
        assert entry.results.total == 100

    def test_creation_snowball(self):
        now = datetime.now()
        entry = LogEntry(
            id="snowball-001",
            type="snowball",
            providers=["semantic_scholar"],
            executed_at=now,
            seed_doi="10.1234/test",
            direction="backward",
        )
        assert entry.type == "snowball"
        assert entry.seed_doi == "10.1234/test"
        assert entry.direction == "backward"

    def test_creation_manual(self):
        now = datetime.now()
        entry = LogEntry(
            id="manual-001",
            type="manual",
            executed_at=now,
            notes="Manually added paper from conference",
        )
        assert entry.type == "manual"
        assert entry.notes == "Manually added paper from conference"

    def test_default_values(self):
        now = datetime.now()
        entry = LogEntry(id="test-001", type="search", executed_at=now)
        assert entry.query is None
        assert entry.providers == []
        assert entry.results is None
        assert entry.seed_doi is None
        assert entry.direction is None
        assert entry.notes is None
        assert entry.subtopics == []
        assert entry.suggested_queries == []
        assert entry.saturation is None

    def test_exploration_fields(self):
        now = datetime.now()
        entry = LogEntry(
            id="explore-001",
            type="exploration",
            query="transformer architectures",
            providers=["openalex", "semantic_scholar"],
            executed_at=now,
            results=SearchResults(total=50, unique=45),
            subtopics=["attention mechanisms", "positional encoding", "layer normalization"],
            suggested_queries=["sparse attention", "efficient transformers", "linear attention"],
            saturation=False,
        )
        assert entry.subtopics == [
            "attention mechanisms",
            "positional encoding",
            "layer normalization",
        ]
        assert entry.suggested_queries == [
            "sparse attention",
            "efficient transformers",
            "linear attention",
        ]
        assert entry.saturation is False

    def test_exploration_saturation_true(self):
        now = datetime.now()
        entry = LogEntry(
            id="explore-002",
            type="exploration",
            query="BERT fine-tuning",
            executed_at=now,
            subtopics=["task-specific layers"],
            suggested_queries=[],
            saturation=True,
        )
        assert entry.saturation is True
        assert entry.subtopics == ["task-specific layers"]
        assert entry.suggested_queries == []

    def test_from_dict(self):
        data = {
            "id": "search-002",
            "type": "search",
            "query": "deep learning",
            "providers": ["arxiv"],
            "executed_at": "2024-01-15T10:30:00",
            "results": {"total": 200, "unique": 180},
        }
        entry = LogEntry.model_validate(data)
        assert entry.id == "search-002"
        assert entry.query == "deep learning"
        assert entry.results.total == 200


class TestPaperEntry:
    """Tests for PaperEntry model."""

    def test_creation(self):
        entry = PaperEntry(
            path="papers/2024/smith-ml.md",
            doi="10.1234/test",
            title="Machine Learning Survey",
            status="included",
            search_ids=["search-001", "search-002"],
        )
        assert entry.path == "papers/2024/smith-ml.md"
        assert entry.doi == "10.1234/test"
        assert entry.title == "Machine Learning Survey"
        assert entry.status == "included"
        assert entry.search_ids == ["search-001", "search-002"]

    def test_default_values(self):
        entry = PaperEntry(path="papers/test.md", doi="10.1234/x", title="Test")
        assert entry.status == "unscreened"
        assert entry.search_ids == []

    def test_from_dict(self):
        data = {
            "path": "papers/paper.md",
            "doi": "10.5678/paper",
            "title": "A Paper",
            "status": "excluded",
            "search_ids": ["s1"],
        }
        entry = PaperEntry.model_validate(data)
        assert entry.status == "excluded"
        assert entry.search_ids == ["s1"]


class TestScreening:
    """Tests for Screening model."""

    def test_creation(self):
        now = datetime.now()
        screening = Screening(status="included", reason="Meets all criteria", screened_at=now)
        assert screening.status == "included"
        assert screening.reason == "Meets all criteria"
        assert screening.screened_at == now

    def test_from_dict(self):
        data = {
            "status": "excluded",
            "reason": "Wrong population",
            "screened_at": "2024-01-20T14:00:00",
        }
        screening = Screening.model_validate(data)
        assert screening.status == "excluded"
        assert screening.reason == "Wrong population"


class TestPaperIndex:
    """Tests for PaperIndex model."""

    def test_creation_minimal(self):
        index = PaperIndex(
            title="Attention Is All You Need",
            authors=["Vaswani", "Shazeer", "Parmar"],
            year=2017,
        )
        assert index.title == "Attention Is All You Need"
        assert index.authors == ["Vaswani", "Shazeer", "Parmar"]
        assert index.year == 2017

    def test_creation_full(self):
        now = datetime.now()
        screening = Screening(status="included", reason="Relevant", screened_at=now)
        index = PaperIndex(
            title="Deep Learning",
            authors=["LeCun", "Bengio", "Hinton"],
            year=2015,
            doi="10.1038/nature14539",
            sources=["openalex", "semantic_scholar"],
            urls={
                "openalex": "https://openalex.org/W123",
                "doi": "https://doi.org/10.1038/nature14539",
            },
            tags=["deep-learning", "review"],
            citations=50000,
            journal="Nature",
            open_access=False,
            pdf="deep-learning.pdf",
            abstract="Deep learning allows computational models...",
            screening=screening,
        )
        assert index.doi == "10.1038/nature14539"
        assert index.sources == ["openalex", "semantic_scholar"]
        assert index.urls["openalex"] == "https://openalex.org/W123"
        assert index.tags == ["deep-learning", "review"]
        assert index.citations == 50000
        assert index.journal == "Nature"
        assert index.open_access is False
        assert index.pdf == "deep-learning.pdf"
        assert index.abstract.startswith("Deep learning")
        assert index.screening.status == "included"

    def test_default_values(self):
        index = PaperIndex(title="Test", authors=["Author"], year=2024)
        assert index.doi is None
        assert index.sources == []
        assert index.urls == {}
        assert index.tags == []
        assert index.citations is None
        assert index.journal is None
        assert index.open_access is None
        assert index.pdf is None
        assert index.abstract is None
        assert index.screening is None
        assert index.subtopic is None
        assert index.relevance is None
        assert index.condensed is None

    def test_exploration_fields(self):
        condensed = Condensed(
            problem="Efficient attention computation",
            method="Linear attention approximation",
            results="O(n) complexity instead of O(n^2)",
            limitations="Some accuracy trade-off",
            relevance_to_exploration="Core technique for efficient transformers",
        )
        index = PaperIndex(
            title="Efficient Transformers: A Survey",
            authors=["Tay", "Dehghani", "Bahri"],
            year=2022,
            doi="10.1145/3530811",
            subtopic="efficient attention",
            relevance="high",
            condensed=condensed,
        )
        assert index.subtopic == "efficient attention"
        assert index.relevance == "high"
        assert index.condensed is not None
        assert index.condensed.problem == "Efficient attention computation"
        assert index.condensed.method == "Linear attention approximation"
        assert index.condensed.results == "O(n) complexity instead of O(n^2)"
        assert index.condensed.limitations == "Some accuracy trade-off"
        assert (
            index.condensed.relevance_to_exploration == "Core technique for efficient transformers"
        )

    def test_relevance_levels(self):
        for relevance_level in ["high", "medium", "low"]:
            index = PaperIndex(
                title="Test Paper",
                authors=["Author"],
                year=2024,
                relevance=relevance_level,
            )
            assert index.relevance == relevance_level

    def test_paper_index_with_nested_condensed_from_dict(self):
        data = {
            "title": "Test Paper with Condensed",
            "authors": ["Smith"],
            "year": 2024,
            "subtopic": "neural scaling",
            "relevance": "medium",
            "condensed": {
                "problem": "Understanding scaling laws",
                "method": "Empirical analysis",
                "results": "Power-law relationships",
                "limitations": "Compute-intensive experiments",
                "relevance_to_exploration": "Foundational for model design",
            },
        }
        index = PaperIndex.model_validate(data)
        assert index.subtopic == "neural scaling"
        assert index.relevance == "medium"
        assert index.condensed is not None
        assert index.condensed.problem == "Understanding scaling laws"
        assert index.condensed.method == "Empirical analysis"
        assert index.condensed.results == "Power-law relationships"
        assert index.condensed.limitations == "Compute-intensive experiments"
        assert index.condensed.relevance_to_exploration == "Foundational for model design"

    def test_from_dict(self):
        data = {
            "title": "Test Paper",
            "authors": ["Smith", "Jones"],
            "year": 2023,
            "doi": "10.1234/test",
            "sources": ["arxiv"],
            "tags": ["ml"],
            "screening": {
                "status": "maybe",
                "reason": "Need more info",
                "screened_at": "2024-02-01T10:00:00",
            },
        }
        index = PaperIndex.model_validate(data)
        assert index.title == "Test Paper"
        assert index.authors == ["Smith", "Jones"]
        assert index.doi == "10.1234/test"
        assert index.screening.status == "maybe"

    def test_to_dict(self):
        index = PaperIndex(
            title="Test",
            authors=["Author"],
            year=2024,
            doi="10.1234/x",
            tags=["tag1"],
        )
        data = index.model_dump()
        assert data["title"] == "Test"
        assert data["authors"] == ["Author"]
        assert data["year"] == 2024
        assert data["doi"] == "10.1234/x"
        assert data["tags"] == ["tag1"]


class TestWorkspaceRoundtrip:
    """Tests for serialization/deserialization roundtrips."""

    def test_slr_roundtrip(self):
        original = SLRWorkspace(
            question="Does X affect Y?",
            framework=Framework(type="pico", fields={"population": "adults", "intervention": "X"}),
            constraints=Constraints(databases=["arxiv", "openalex"], year_range="2020-2024"),
            stats=Stats(total=100, included=50),
            inclusion=["RCT", "meta-analysis"],
            exclusion=["case study"],
        )
        data = original.model_dump()
        restored = SLRWorkspace.model_validate(data)
        assert restored.question == original.question
        assert restored.framework.type == original.framework.type
        assert restored.constraints.databases == original.constraints.databases
        assert restored.stats.total == original.stats.total
        assert restored.inclusion == original.inclusion

    def test_exploration_roundtrip(self):
        now = datetime.now()
        original = ExplorationWorkspace(
            question="AI trends",
            constraints=Constraints(year_range="2023-2024"),
            limit=500,
            started_at=now,
        )
        data = original.model_dump()
        restored = ExplorationWorkspace.model_validate(data)
        assert restored.question == original.question
        assert restored.limit == original.limit
        assert restored.started_at == original.started_at

    def test_collection_roundtrip(self):
        original = CollectionWorkspace(
            question="My papers",
            stats=Stats(total=25, with_pdf=20),
        )
        data = original.model_dump()
        restored = CollectionWorkspace.model_validate(data)
        assert restored.question == original.question
        assert restored.stats.total == original.stats.total

    def test_paper_index_roundtrip(self):
        now = datetime.now()
        original = PaperIndex(
            title="Test Paper",
            authors=["Author One", "Author Two"],
            year=2024,
            doi="10.1234/test",
            sources=["openalex"],
            urls={"doi": "https://doi.org/10.1234/test"},
            tags=["ml", "ai"],
            citations=100,
            screening=Screening(status="included", reason="Good paper", screened_at=now),
        )
        data = original.model_dump()
        restored = PaperIndex.model_validate(data)
        assert restored.title == original.title
        assert restored.authors == original.authors
        assert restored.doi == original.doi
        assert restored.screening.status == original.screening.status

    def test_paper_index_with_exploration_fields_roundtrip(self):
        condensed = Condensed(
            problem="Roundtrip test problem",
            method="Roundtrip test method",
            results="Roundtrip test results",
            limitations="Roundtrip test limitations",
            relevance_to_exploration="Roundtrip test relevance",
        )
        original = PaperIndex(
            title="Exploration Paper",
            authors=["Explorer"],
            year=2024,
            subtopic="test subtopic",
            relevance="high",
            condensed=condensed,
        )
        data = original.model_dump()
        restored = PaperIndex.model_validate(data)
        assert restored.subtopic == original.subtopic
        assert restored.relevance == original.relevance
        assert restored.condensed is not None
        assert restored.condensed.problem == original.condensed.problem
        assert restored.condensed.method == original.condensed.method
        assert restored.condensed.results == original.condensed.results
        assert restored.condensed.limitations == original.condensed.limitations
        assert (
            restored.condensed.relevance_to_exploration
            == original.condensed.relevance_to_exploration
        )
