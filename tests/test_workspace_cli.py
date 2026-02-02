"""Tests for workspace CLI commands."""

import pytest
import yaml

from scimesh.cli import app
from scimesh.workspace.cli import workspace_screen
from scimesh.workspace.models import ExplorationWorkspace, PaperEntry
from scimesh.workspace.repository import YamlWorkspaceRepository


def test_workspace_init_exploration(tmp_path, capsys):
    """Test workspace init creates exploration workspace."""
    workspace_path = tmp_path / "my-exploration"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "exploration",
                "--question",
                "What is the state of diffusion models?",
            ]
        )

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Workspace created" in captured.out

    index = yaml.safe_load((workspace_path / "index.yaml").read_text())
    assert index["type"] == "exploration"
    assert index["question"] == "What is the state of diffusion models?"
    assert "started_at" in index
    assert index["started_at"] is not None

    assert (workspace_path / "log.yaml").exists()
    assert (workspace_path / "papers.yaml").exists()


def test_workspace_init_slr(tmp_path, capsys):
    """Test workspace init creates SLR workspace."""
    workspace_path = tmp_path / "my-slr"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "slr",
                "--question",
                "What are the effects of X on Y?",
                "--framework",
                "pico",
            ]
        )

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Workspace created" in captured.out

    index = yaml.safe_load((workspace_path / "index.yaml").read_text())
    assert index["type"] == "slr"
    assert index["question"] == "What are the effects of X on Y?"
    assert index["framework"]["type"] == "pico"


def test_workspace_init_collection(tmp_path, capsys):
    """Test workspace init creates collection workspace."""
    workspace_path = tmp_path / "my-collection"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "collection",
                "--question",
                "Papers on transformers",
            ]
        )

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Workspace created" in captured.out

    index = yaml.safe_load((workspace_path / "index.yaml").read_text())
    assert index["type"] == "collection"
    assert index["question"] == "Papers on transformers"


def test_workspace_init_with_limit(tmp_path):
    """Test workspace init with --limit for exploration."""
    workspace_path = tmp_path / "limited-exploration"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "exploration",
                "--question",
                "Limited search",
                "--limit",
                "50",
            ]
        )

    assert exc_info.value.code == 0

    index = yaml.safe_load((workspace_path / "index.yaml").read_text())
    assert index["type"] == "exploration"
    assert index["limit"] == 50


def test_workspace_init_with_databases_and_year_range(tmp_path):
    """Test workspace init with custom databases and year range."""
    workspace_path = tmp_path / "my-workspace"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "exploration",
                "--question",
                "Test",
                "--databases",
                "arxiv,scopus",
                "--year-range",
                "2020-2024",
            ]
        )

    assert exc_info.value.code == 0

    index = yaml.safe_load((workspace_path / "index.yaml").read_text())
    assert index["constraints"]["databases"] == ["arxiv", "scopus"]
    assert index["constraints"]["year_range"] == "2020-2024"


def test_workspace_init_fails_if_exists(tmp_path, capsys):
    """Test workspace init fails when workspace already exists."""
    workspace_path = tmp_path / "existing"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "exploration",
                "--question",
                "First",
            ]
        )
    assert exc_info.value.code == 0

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "exploration",
                "--question",
                "Second",
            ]
        )
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err


def test_workspace_init_invalid_type(tmp_path, capsys):
    """Test workspace init with invalid type."""
    workspace_path = tmp_path / "invalid"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "invalid",
                "--question",
                "Test",
            ]
        )

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Invalid workspace type" in captured.err


def test_workspace_stats_shows_totals(tmp_path, capsys):
    """Test workspace stats displays workspace info and totals."""
    workspace_path = tmp_path / "my-workspace"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "exploration",
                "--question",
                "Diffusion models for imputation",
            ]
        )
    assert exc_info.value.code == 0

    with pytest.raises(SystemExit) as exc_info:
        app(["workspace", "stats", str(workspace_path)])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "exploration" in captured.out.lower()
    assert "Diffusion models for imputation" in captured.out
    assert "Total papers: 0" in captured.out


def test_workspace_stats_not_found(tmp_path, capsys):
    """Test workspace stats fails when workspace not found."""
    workspace_path = tmp_path / "nonexistent"

    with pytest.raises(SystemExit) as exc_info:
        app(["workspace", "stats", str(workspace_path)])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err


def test_workspace_stats_slr_shows_framework(tmp_path, capsys):
    """Test workspace stats shows framework info for SLR."""
    workspace_path = tmp_path / "slr-workspace"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "slr",
                "--question",
                "Effects of X",
                "--framework",
                "pico",
            ]
        )
    assert exc_info.value.code == 0

    with pytest.raises(SystemExit) as exc_info:
        app(["workspace", "stats", str(workspace_path)])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "slr" in captured.out.lower()
    assert "pico" in captured.out.lower()


def test_workspace_init_default_type_is_exploration(tmp_path):
    """Test workspace init defaults to exploration type."""
    workspace_path = tmp_path / "default"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--question",
                "Default type",
            ]
        )

    assert exc_info.value.code == 0

    index = yaml.safe_load((workspace_path / "index.yaml").read_text())
    assert index["type"] == "exploration"


def test_workspace_list_empty_shows_no_papers(tmp_path, capsys):
    """Test workspace list shows 'No papers found.' for empty workspace."""
    workspace_path = tmp_path / "empty-workspace"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "exploration",
                "--question",
                "Test question",
            ]
        )
    assert exc_info.value.code == 0

    with pytest.raises(SystemExit) as exc_info:
        app(["workspace", "list", str(workspace_path)])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "No papers found." in captured.out


def test_workspace_finish_sets_finished_at(tmp_path, capsys):
    """Test workspace finish sets finished_at timestamp."""
    workspace_path = tmp_path / "finish-workspace"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "exploration",
                "--question",
                "Test question",
            ]
        )
    assert exc_info.value.code == 0

    index = yaml.safe_load((workspace_path / "index.yaml").read_text())
    assert index.get("finished_at") is None

    with pytest.raises(SystemExit) as exc_info:
        app(["workspace", "finish", str(workspace_path)])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Workspace finished" in captured.out

    index = yaml.safe_load((workspace_path / "index.yaml").read_text())
    assert index["finished_at"] is not None


def test_workspace_finish_fails_for_non_exploration(tmp_path, capsys):
    """Test workspace finish fails for non-exploration workspace."""
    workspace_path = tmp_path / "slr-workspace"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "workspace",
                "init",
                str(workspace_path),
                "--type",
                "slr",
                "--question",
                "Test question",
                "--framework",
                "pico",
            ]
        )
    assert exc_info.value.code == 0

    with pytest.raises(SystemExit) as exc_info:
        app(["workspace", "finish", str(workspace_path)])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "finish command is only for exploration workspaces" in captured.err


def test_workspace_search_not_found(tmp_path, capsys):
    """Test workspace search fails when workspace not found."""
    workspace_path = tmp_path / "nonexistent"

    with pytest.raises(SystemExit) as exc_info:
        app(["workspace", "search", str(workspace_path), "diffusion models"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Workspace not found" in captured.err


def test_workspace_screen_include(tmp_path):
    """Test screening a paper as included."""
    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(question="Test")
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers(
        [PaperEntry(path="papers/2024/test-paper", doi="10.1234/test", title="Test Paper")]
    )

    paper_dir = tmp_path / "papers/2024/test-paper"
    paper_dir.mkdir(parents=True)
    (paper_dir / "index.yaml").write_text("title: Test Paper\nauthors: [Test]\nyear: 2024\n")

    workspace_screen(
        tmp_path,
        include=["test-paper:Relevant to research question"],
        exclude=None,
        maybe=None,
    )

    papers = repo.load_papers()
    assert papers[0].status == "included"

    paper = repo.load_paper("papers/2024/test-paper")
    assert paper.screening is not None
    assert paper.screening.status == "included"


def test_workspace_screen_exclude(tmp_path):
    """Test screening a paper as excluded."""
    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(question="Test")
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers(
        [PaperEntry(path="papers/2024/test-paper", doi="10.1234/test", title="Test Paper")]
    )

    paper_dir = tmp_path / "papers/2024/test-paper"
    paper_dir.mkdir(parents=True)
    (paper_dir / "index.yaml").write_text("title: Test Paper\nauthors: [Test]\nyear: 2024\n")

    workspace_screen(
        tmp_path,
        include=None,
        exclude=["test-paper:Off topic"],
        maybe=None,
    )

    papers = repo.load_papers()
    assert papers[0].status == "excluded"


def test_workspace_screen_updates_stats(tmp_path):
    """Test that screening updates workspace stats."""
    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(question="Test")
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers(
        [
            PaperEntry(path="papers/2024/paper1", doi="10.1234/1", title="Paper 1"),
            PaperEntry(path="papers/2024/paper2", doi="10.1234/2", title="Paper 2"),
        ]
    )

    for name in ["paper1", "paper2"]:
        paper_dir = tmp_path / f"papers/2024/{name}"
        paper_dir.mkdir(parents=True)
        (paper_dir / "index.yaml").write_text(f"title: {name}\nauthors: [Test]\nyear: 2024\n")

    workspace_screen(
        tmp_path,
        include=["paper1:Good"],
        exclude=["paper2:Bad"],
        maybe=None,
    )

    workspace = repo.load()
    assert workspace.stats.included == 1
    assert workspace.stats.excluded == 1


def test_workspace_snowball_not_found(tmp_path):
    """Test snowball command on non-existent workspace."""
    from scimesh.workspace.cli import workspace_snowball

    with pytest.raises(SystemExit):
        workspace_snowball(
            tmp_path,
            paper_id="10.1234/test",
            direction="both",
            providers=None,
            max_results=10,
            scihub=False,
        )


def test_workspace_export_bibtex(tmp_path, capsys):
    """Test exporting papers to BibTeX."""
    from scimesh.workspace.cli import workspace_export

    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(question="Test")
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers([PaperEntry(path="papers/2024/test", doi="10.1234/test", title="Test Paper")])

    paper_dir = tmp_path / "papers/2024/test"
    paper_dir.mkdir(parents=True)
    (paper_dir / "index.yaml").write_text(
        "title: Test Paper\nauthors: [John Doe]\nyear: 2024\ndoi: 10.1234/test\n"
    )

    workspace_export(tmp_path, output=None, format="bibtex", status=None)

    captured = capsys.readouterr()
    assert "@article" in captured.out or "@misc" in captured.out
    assert "Test Paper" in captured.out


def test_workspace_set_question(tmp_path):
    """Test setting workspace question."""
    from scimesh.workspace.cli import workspace_set

    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(question="Old question")
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers([])

    workspace_set(tmp_path, question="New question", limit=None, databases=None, year_range=None)

    updated = repo.load()
    assert updated.question == "New question"


def test_workspace_set_limit(tmp_path):
    """Test setting exploration limit."""
    from scimesh.workspace.cli import workspace_set

    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(question="Test", limit=100)
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers([])

    workspace_set(tmp_path, question=None, limit=500, databases=None, year_range=None)

    updated = repo.load()
    assert updated.limit == 500


def test_workspace_add_inclusion_slr(tmp_path):
    """Test adding inclusion criteria to SLR workspace."""
    from scimesh.workspace.cli import workspace_add_inclusion
    from scimesh.workspace.models import Framework, SLRWorkspace

    repo = YamlWorkspaceRepository(tmp_path)
    workspace = SLRWorkspace(
        question="Test",
        framework=Framework(type="pico"),
        inclusion=["Existing criterion"],
    )
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers([])

    workspace_add_inclusion(tmp_path, criteria=["New criterion 1", "New criterion 2"])

    updated = repo.load()
    assert "New criterion 1" in updated.inclusion
    assert "New criterion 2" in updated.inclusion
    assert "Existing criterion" in updated.inclusion


def test_workspace_add_inclusion_fails_for_exploration(tmp_path):
    """Test that add-inclusion fails for exploration workspace."""
    from scimesh.workspace.cli import workspace_add_inclusion

    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(question="Test")
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers([])

    with pytest.raises(SystemExit):
        workspace_add_inclusion(tmp_path, criteria=["Some criterion"])


def test_workspace_add_exclusion_slr(tmp_path):
    """Test adding exclusion criteria to SLR workspace."""
    from scimesh.workspace.cli import workspace_add_exclusion
    from scimesh.workspace.models import Framework, SLRWorkspace

    repo = YamlWorkspaceRepository(tmp_path)
    workspace = SLRWorkspace(
        question="Test",
        framework=Framework(type="pico"),
        exclusion=["Existing criterion"],
    )
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers([])

    workspace_add_exclusion(tmp_path, criteria=["New criterion 1", "New criterion 2"])

    updated = repo.load()
    assert "New criterion 1" in updated.exclusion
    assert "New criterion 2" in updated.exclusion
    assert "Existing criterion" in updated.exclusion


def test_workspace_add_exclusion_fails_for_exploration(tmp_path):
    """Test that add-exclusion fails for exploration workspace."""
    from scimesh.workspace.cli import workspace_add_exclusion

    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(question="Test")
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers([])

    with pytest.raises(SystemExit):
        workspace_add_exclusion(tmp_path, criteria=["Some criterion"])


def test_workspace_prisma(tmp_path, capsys):
    """Test PRISMA generation."""
    from scimesh.workspace.cli import workspace_prisma
    from scimesh.workspace.models import Stats

    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(
        question="Test question",
        stats=Stats(total=10, included=5, excluded=3, maybe=1, unscreened=1),
    )
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers([])

    workspace_prisma(tmp_path, output=None)

    captured = capsys.readouterr()
    assert "PRISMA" in captured.out or "flowchart" in captured.out
    assert "Test question" in captured.out


def test_workspace_update_stats(tmp_path, capsys):
    """Test update-stats command."""
    from scimesh.workspace.cli import workspace_update_stats
    from scimesh.workspace.models import Stats

    repo = YamlWorkspaceRepository(tmp_path)
    workspace = ExplorationWorkspace(question="Test", stats=Stats(total=0))
    repo.save(workspace)
    repo.save_log([])
    repo.save_papers(
        [PaperEntry(path="papers/2024/test", doi="10.1234/test", title="Test", status="included")]
    )

    paper_dir = tmp_path / "papers/2024/test"
    paper_dir.mkdir(parents=True)
    (paper_dir / "index.yaml").write_text("title: Test\nauthors: [Test]\nyear: 2024\n")
    (paper_dir / "fulltext.pdf").write_bytes(b"fake pdf")

    workspace_update_stats(tmp_path)

    captured = capsys.readouterr()
    assert "Total: 1" in captured.out
    assert "With PDF: 1" in captured.out
    assert "Included: 1" in captured.out
