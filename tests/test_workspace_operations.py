"""Tests for workspace operations."""

from datetime import UTC, datetime

from scimesh.export.paper_exporter import get_paper_path
from scimesh.models import Paper
from scimesh.workspace.models import ExplorationWorkspace, LogEntry, PaperEntry
from scimesh.workspace.operations import ingest_papers
from scimesh.workspace.repository import YamlWorkspaceRepository


def test_ingest_papers_logs_total_and_unique_counts(tmp_path):
    repo = YamlWorkspaceRepository(tmp_path)
    repo.save(ExplorationWorkspace(question="q"))
    papers = [Paper(title=f"Paper {i}", authors=(), year=2024, source="openalex") for i in range(3)]
    _, existing_path = get_paper_path(papers[0], tmp_path)
    repo.save_papers([PaperEntry(path=existing_path, doi="", title="Paper 0")])

    new_count = ingest_papers(
        repo,
        papers,
        tmp_path,
        LogEntry(
            id="s1", type="search", query="q", providers=["openalex"], executed_at=datetime.now(UTC)
        ),
    )

    assert new_count == 2
    [entry] = repo.load_log()
    assert entry.results is not None
    assert (entry.results.total, entry.results.unique) == (3, 2)
    assert [p.search_ids for p in repo.load_papers()[1:]] == [["s1"], ["s1"]]
