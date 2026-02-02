"""Tests for workspace CLI commands."""

import pytest
import yaml

from scimesh.cli import app


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
