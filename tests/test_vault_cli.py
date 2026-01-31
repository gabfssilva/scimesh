# tests/test_vault_cli.py
"""Tests for vault CLI commands."""

import pytest
import yaml

from scimesh.cli import app


def test_vault_init_with_framework_pico(tmp_path):
    """Test vault init with --framework pico."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "What is the effect?",
                "--framework",
                "pico",
                "--population",
                "Patients",
                "--intervention",
                "Drug X",
                "--comparison",
                "Placebo",
                "--outcome",
                "Recovery rate",
            ]
        )

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["question"] == "What is the effect?"
    assert index["protocol"]["framework"]["type"] == "pico"
    assert index["protocol"]["framework"]["fields"]["population"] == "Patients"
    assert index["protocol"]["framework"]["fields"]["intervention"] == "Drug X"
    assert index["protocol"]["framework"]["fields"]["comparison"] == "Placebo"
    assert index["protocol"]["framework"]["fields"]["outcome"] == "Recovery rate"


def test_vault_init_with_framework_custom(tmp_path):
    """Test vault init with --framework custom and --field."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "How do methods compare?",
                "--framework",
                "custom",
                "--field",
                "task:Imputation",
                "--field",
                "method:Diffusion",
                "--field",
                "metrics:RMSE",
            ]
        )

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["framework"]["type"] == "custom"
    assert index["protocol"]["framework"]["fields"]["task"] == "Imputation"
    assert index["protocol"]["framework"]["fields"]["method"] == "Diffusion"
    assert index["protocol"]["framework"]["fields"]["metrics"] == "RMSE"


def test_vault_init_with_framework_spider(tmp_path):
    """Test vault init with --framework spider."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "How do students experience X?",
                "--framework",
                "spider",
                "--sample",
                "Graduate students",
                "--phenomenon",
                "Online learning",
                "--design",
                "Phenomenological",
                "--evaluation",
                "Thematic analysis",
                "--research-type",
                "Qualitative",
            ]
        )

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["framework"]["type"] == "spider"
    assert index["protocol"]["framework"]["fields"]["sample"] == "Graduate students"
    assert index["protocol"]["framework"]["fields"]["phenomenon"] == "Online learning"
    assert index["protocol"]["framework"]["fields"]["design"] == "Phenomenological"
    assert index["protocol"]["framework"]["fields"]["evaluation"] == "Thematic analysis"
    assert index["protocol"]["framework"]["fields"]["research_type"] == "Qualitative"


def test_vault_init_default_framework_is_custom(tmp_path):
    """Test vault init without framework defaults to custom."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "init", str(vault_path), "--question", "Simple question"])

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["framework"]["type"] == "custom"
    assert index["protocol"]["framework"]["fields"] == {}


def test_vault_init_pico_partial_fields(tmp_path):
    """Test vault init with PICO framework and partial fields."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "What is the effect?",
                "--framework",
                "pico",
                "--population",
                "Adults",
                "--outcome",
                "Mortality",
            ]
        )

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["framework"]["type"] == "pico"
    assert index["protocol"]["framework"]["fields"]["population"] == "Adults"
    assert index["protocol"]["framework"]["fields"]["outcome"] == "Mortality"
    # Ensure missing fields are not present (not empty strings)
    assert "intervention" not in index["protocol"]["framework"]["fields"]
    assert "comparison" not in index["protocol"]["framework"]["fields"]


def test_vault_init_with_inclusion_exclusion(tmp_path):
    """Test vault init with inclusion and exclusion criteria."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "Test question",
                "--framework",
                "pico",
                "--inclusion",
                "RCT studies",
                "--inclusion",
                "Peer-reviewed",
                "--exclusion",
                "Case studies",
            ]
        )

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert "RCT studies" in index["protocol"]["inclusion"]
    assert "Peer-reviewed" in index["protocol"]["inclusion"]
    assert "Case studies" in index["protocol"]["exclusion"]


def test_vault_init_with_databases_and_year_range(tmp_path):
    """Test vault init with custom databases and year range."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "Test question",
                "--databases",
                "arxiv,openalex",
                "--year-range",
                "2020-2024",
            ]
        )

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["databases"] == ["arxiv", "openalex"]
    assert index["protocol"]["year_range"] == "2020-2024"


def test_vault_init_invalid_framework(tmp_path, capsys):
    """Test vault init with invalid framework type."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "init", str(vault_path), "--question", "Test", "--framework", "invalid"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Invalid framework type" in captured.err


def test_vault_init_custom_field_invalid_format(tmp_path, capsys):
    """Test vault init with invalid custom field format (warning)."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "Test",
                "--framework",
                "custom",
                "--field",
                "valid:value",
                "--field",
                "invalid_no_colon",
            ]
        )

    # Should still succeed but with warning
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    err_lower = captured.err.lower()
    assert "invalid field format" in err_lower or "expected format" in err_lower

    # Valid field should still be present
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["framework"]["fields"]["valid"] == "value"


def test_vault_init_vault_already_exists(tmp_path, capsys):
    """Test vault init fails when vault already exists."""
    vault_path = tmp_path / "review"

    # First init should succeed
    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "init", str(vault_path), "--question", "First question"])
    assert exc_info.value.code == 0

    # Second init should fail
    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "init", str(vault_path), "--question", "Second question"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err


def test_vault_set_field(tmp_path):
    """Test vault set --field to modify framework fields."""
    vault_path = tmp_path / "review"

    # First create vault
    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "RQ",
                "--framework",
                "pico",
                "--population",
                "Initial",
            ]
        )
    assert exc_info.value.code == 0

    # Then modify
    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "set", str(vault_path), "--field", "population:Updated population"])

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["framework"]["fields"]["population"] == "Updated population"


def test_vault_set_multiple_fields(tmp_path):
    """Test vault set with multiple --field options."""
    vault_path = tmp_path / "review"

    # Create vault
    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "init", str(vault_path), "--question", "RQ", "--framework", "pico"])
    assert exc_info.value.code == 0

    # Set multiple fields
    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "set",
                str(vault_path),
                "--field",
                "population:Patients",
                "--field",
                "intervention:Drug X",
                "--field",
                "outcome:Recovery",
            ]
        )

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["framework"]["fields"]["population"] == "Patients"
    assert index["protocol"]["framework"]["fields"]["intervention"] == "Drug X"
    assert index["protocol"]["framework"]["fields"]["outcome"] == "Recovery"


def test_vault_set_change_framework(tmp_path):
    """Test vault set --framework to change framework type."""
    vault_path = tmp_path / "review"

    # Create vault with PICO
    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "RQ",
                "--framework",
                "pico",
                "--population",
                "Initial",
            ]
        )
    assert exc_info.value.code == 0

    # Change to SPIDER framework
    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "set",
                str(vault_path),
                "--framework",
                "spider",
                "--field",
                "sample:Graduate students",
            ]
        )

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["framework"]["type"] == "spider"
    assert index["protocol"]["framework"]["fields"]["sample"] == "Graduate students"
    # Old PICO fields should be gone
    assert "population" not in index["protocol"]["framework"]["fields"]


def test_vault_set_question_and_year_range(tmp_path):
    """Test vault set for question and year_range."""
    vault_path = tmp_path / "review"

    # Create vault
    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "init", str(vault_path), "--question", "Original question"])
    assert exc_info.value.code == 0

    # Update question and year range
    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "set",
                str(vault_path),
                "--question",
                "Updated question",
                "--year-range",
                "2020-2025",
            ]
        )

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert index["protocol"]["question"] == "Updated question"
    assert index["protocol"]["year_range"] == "2020-2025"


def test_vault_add_inclusion_with_new_protocol(tmp_path):
    """Test add-inclusion works with new Protocol structure."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "init", str(vault_path), "--question", "RQ", "--framework", "pico"])
    assert exc_info.value.code == 0

    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "add-inclusion", str(vault_path), "Must use deep learning"])

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert "Must use deep learning" in index["protocol"]["inclusion"]
    assert index["protocol"]["framework"]["type"] == "pico"


def test_vault_add_exclusion_with_new_protocol(tmp_path):
    """Test add-exclusion works with new Protocol structure."""
    vault_path = tmp_path / "review"

    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "init", str(vault_path), "--question", "RQ", "--framework", "spider"])
    assert exc_info.value.code == 0

    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "add-exclusion", str(vault_path), "Survey papers"])

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    assert "Survey papers" in index["protocol"]["exclusion"]
    assert index["protocol"]["framework"]["type"] == "spider"


def test_vault_add_inclusion_preserves_framework_fields(tmp_path):
    """Test add-inclusion preserves existing framework fields."""
    vault_path = tmp_path / "review"

    # Create vault with PICO fields
    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "RQ",
                "--framework",
                "pico",
                "--population",
                "Adults",
                "--intervention",
                "Exercise",
            ]
        )
    assert exc_info.value.code == 0

    # Add inclusion criteria
    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "add-inclusion", str(vault_path), "RCT only"])

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    # Verify framework fields are preserved
    assert index["protocol"]["framework"]["fields"]["population"] == "Adults"
    assert index["protocol"]["framework"]["fields"]["intervention"] == "Exercise"
    # And inclusion was added
    assert "RCT only" in index["protocol"]["inclusion"]


def test_vault_add_exclusion_preserves_framework_fields(tmp_path):
    """Test add-exclusion preserves existing framework fields."""
    vault_path = tmp_path / "review"

    # Create vault with custom fields
    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "vault",
                "init",
                str(vault_path),
                "--question",
                "RQ",
                "--framework",
                "custom",
                "--field",
                "domain:Healthcare",
                "--field",
                "method:ML",
            ]
        )
    assert exc_info.value.code == 0

    # Add exclusion criteria
    with pytest.raises(SystemExit) as exc_info:
        app(["vault", "add-exclusion", str(vault_path), "Non-English"])

    assert exc_info.value.code == 0
    index = yaml.safe_load((vault_path / "index.yaml").read_text())
    # Verify framework fields are preserved
    assert index["protocol"]["framework"]["fields"]["domain"] == "Healthcare"
    assert index["protocol"]["framework"]["fields"]["method"] == "ML"
    # And exclusion was added
    assert "Non-English" in index["protocol"]["exclusion"]
