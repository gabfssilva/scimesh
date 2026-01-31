# scimesh/vault/operations.py
"""Vault operations for loading, saving, and updating vaults."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from scimesh.vault.models import (
    PaperEntry,
    Protocol,
    ScreeningDecision,
    ScreeningStatus,
    SearchEntry,
    VaultIndex,
    VaultStats,
)


class VaultError(Exception):
    """Error during vault operations."""


class VaultNotFoundError(VaultError):
    """Vault index.yaml not found."""


class VaultExistsError(VaultError):
    """Vault already exists."""


def load_vault(vault_path: Path) -> VaultIndex:
    """Load vault index from directory.

    Args:
        vault_path: Path to vault directory.

    Returns:
        VaultIndex with all data.

    Raises:
        VaultNotFoundError: If index.yaml doesn't exist.
    """
    index_path = vault_path / "index.yaml"
    if not index_path.exists():
        raise VaultNotFoundError(f"Vault not found: {vault_path}")

    data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    return VaultIndex.from_dict(data or {})


def save_vault(vault_path: Path, vault: VaultIndex) -> None:
    """Save vault index to directory.

    Args:
        vault_path: Path to vault directory.
        vault: VaultIndex to save.
    """
    vault_path.mkdir(parents=True, exist_ok=True)
    index_path = vault_path / "index.yaml"

    data = vault.to_dict()
    yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    index_path.write_text(yaml_content, encoding="utf-8")


def generate_search_id(query: str, providers: list[str]) -> str:
    """Generate deterministic search ID from query and providers.

    Args:
        query: Search query string.
        providers: List of provider names.

    Returns:
        12-character hex string: MD5(query + providers + YYYY-MM)[:12]
    """
    now = datetime.now(UTC)
    year_month = now.strftime("%Y-%m")
    content = query + ",".join(sorted(providers)) + year_month
    return hashlib.md5(content.encode()).hexdigest()[:12]


def load_searches(vault_path: Path) -> list[SearchEntry]:
    """Load searches from searches.yaml.

    Args:
        vault_path: Path to vault directory.

    Returns:
        List of SearchEntry objects.
    """
    searches_path = vault_path / "searches.yaml"
    if not searches_path.exists():
        return []

    data = yaml.safe_load(searches_path.read_text(encoding="utf-8"))
    if not data:
        return []

    return [SearchEntry.from_dict(entry) for entry in data]


def save_searches(vault_path: Path, searches: list[SearchEntry]) -> None:
    """Save searches to searches.yaml.

    Args:
        vault_path: Path to vault directory.
        searches: List of SearchEntry objects.
    """
    searches_path = vault_path / "searches.yaml"
    data = [entry.to_dict() for entry in searches]
    yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    searches_path.write_text(yaml_content, encoding="utf-8")


def load_papers_index(vault_path: Path) -> list[PaperEntry]:
    """Load papers from papers.yaml.

    Args:
        vault_path: Path to vault directory.

    Returns:
        List of PaperEntry objects.
    """
    papers_path = vault_path / "papers.yaml"
    if not papers_path.exists():
        return []

    data = yaml.safe_load(papers_path.read_text(encoding="utf-8"))
    if not data:
        return []

    return [PaperEntry.from_dict(entry) for entry in data]


def save_papers_index(vault_path: Path, papers: list[PaperEntry]) -> None:
    """Save papers to papers.yaml.

    Args:
        vault_path: Path to vault directory.
        papers: List of PaperEntry objects.
    """
    papers_path = vault_path / "papers.yaml"
    data = [entry.to_dict() for entry in papers]
    yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    papers_path.write_text(yaml_content, encoding="utf-8")


def add_search(vault_path: Path, entry: SearchEntry) -> None:
    """Add a search entry to searches.yaml if ID doesn't exist.

    Args:
        vault_path: Path to vault directory.
        entry: SearchEntry to add.
    """
    searches = load_searches(vault_path)
    existing_ids = {s.id for s in searches}
    if entry.id not in existing_ids:
        searches.append(entry)
        save_searches(vault_path, searches)


def add_papers_from_search(
    vault_path: Path,
    papers: list[PaperEntry],
    search_id: str,
) -> tuple[int, int]:
    """Add papers from a search, deduplicating by path.

    Args:
        vault_path: Path to vault directory.
        papers: List of PaperEntry objects to add.
        search_id: ID of the search these papers came from.

    Returns:
        Tuple of (total papers in search, unique new papers added).
    """
    existing = load_papers_index(vault_path)
    existing_paths = {p.path for p in existing}

    # Update existing papers with new search_id
    updated_existing: list[PaperEntry] = []
    for paper in existing:
        if paper.path in {p.path for p in papers}:
            # Add search_id to existing paper
            new_search_ids = tuple(set(paper.search_ids) | {search_id})
            updated_existing.append(
                PaperEntry(
                    path=paper.path,
                    doi=paper.doi,
                    title=paper.title,
                    status=paper.status,
                    search_ids=new_search_ids,
                )
            )
        else:
            updated_existing.append(paper)

    # Add new papers
    new_papers: list[PaperEntry] = []
    for paper in papers:
        if paper.path not in existing_paths:
            new_papers.append(
                PaperEntry(
                    path=paper.path,
                    doi=paper.doi,
                    title=paper.title,
                    status=paper.status,
                    search_ids=(search_id,),
                )
            )

    all_papers = updated_existing + new_papers
    save_papers_index(vault_path, all_papers)

    return len(papers), len(new_papers)


def load_paper(paper_path: Path) -> dict[str, Any]:
    """Load paper index.yaml.

    Args:
        paper_path: Path to paper directory.

    Returns:
        Paper data dictionary.

    Raises:
        FileNotFoundError: If index.yaml doesn't exist.
    """
    index_path = paper_path / "index.yaml"
    if not index_path.exists():
        raise FileNotFoundError(f"Paper index not found: {paper_path}")

    data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    return data or {}


def save_paper(paper_path: Path, data: dict[str, Any]) -> None:
    """Save paper index.yaml.

    Args:
        paper_path: Path to paper directory.
        data: Paper data dictionary.
    """
    paper_path.mkdir(parents=True, exist_ok=True)
    index_path = paper_path / "index.yaml"

    yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    index_path.write_text(yaml_content, encoding="utf-8")


def set_paper_screening(
    vault_path: Path,
    paper_path: Path,
    status: ScreeningStatus,
    reason: str,
) -> ScreeningDecision:
    """Set screening status for a paper.

    Args:
        vault_path: Path to vault directory.
        paper_path: Path to paper directory.
        status: Screening status to set.
        reason: Reason for the decision.

    Returns:
        The ScreeningDecision that was applied.
    """
    data = load_paper(paper_path)

    now = datetime.now(UTC)
    decision = ScreeningDecision(status=status, reason=reason, screened_at=now)

    data["screening"] = {
        "status": status.value,
        "reason": reason,
        "screened_at": now.isoformat().replace("+00:00", "Z"),
    }

    save_paper(paper_path, data)

    # Update status in papers.yaml
    papers = load_papers_index(vault_path)
    paper_slug = paper_path.name
    updated_papers = [
        PaperEntry(
            path=p.path,
            doi=p.doi,
            title=p.title,
            status=status if p.path == paper_slug else p.status,
            search_ids=p.search_ids,
        )
        for p in papers
    ]
    save_papers_index(vault_path, updated_papers)

    return decision


def update_vault_stats(vault_path: Path) -> VaultStats:
    """Recalculate and update vault statistics.

    Scans all paper directories and counts statuses.

    Args:
        vault_path: Path to vault directory.

    Returns:
        Updated VaultStats.
    """
    vault = load_vault(vault_path)
    papers = load_papers_index(vault_path)

    total = 0
    included = 0
    excluded = 0
    maybe = 0
    unscreened = 0
    with_pdf = 0

    updated_papers: list[PaperEntry] = []

    for paper_entry in papers:
        paper_path = vault_path / paper_entry.path
        if not paper_path.exists():
            continue

        total += 1

        # Check for PDF
        if (paper_path / "fulltext.pdf").exists():
            with_pdf += 1

        # Get screening status from paper index
        try:
            paper_data = load_paper(paper_path)
            screening = paper_data.get("screening", {})
            status_str = screening.get("status", "unscreened")
            try:
                status = ScreeningStatus(status_str)
            except ValueError:
                status = ScreeningStatus.UNSCREENED
        except FileNotFoundError:
            status = ScreeningStatus.UNSCREENED

        # Count by status
        if status == ScreeningStatus.INCLUDED:
            included += 1
        elif status == ScreeningStatus.EXCLUDED:
            excluded += 1
        elif status == ScreeningStatus.MAYBE:
            maybe += 1
        else:
            unscreened += 1

        # Update paper entry with current status
        updated_papers.append(
            PaperEntry(
                path=paper_entry.path,
                doi=paper_entry.doi,
                title=paper_entry.title,
                status=status,
                search_ids=paper_entry.search_ids,
            )
        )

    now = datetime.now(UTC)
    new_stats = VaultStats(
        total=total,
        included=included,
        excluded=excluded,
        maybe=maybe,
        unscreened=unscreened,
        with_pdf=with_pdf,
        last_updated=now,
    )

    # Update vault with new stats
    updated_vault = VaultIndex(
        protocol=vault.protocol,
        stats=new_stats,
    )
    save_vault(vault_path, updated_vault)

    # Update papers.yaml with current statuses
    save_papers_index(vault_path, updated_papers)

    return new_stats


def init_vault(
    vault_path: Path,
    protocol: Protocol,
) -> VaultIndex:
    """Initialize a new vault with protocol.

    Args:
        vault_path: Path to vault directory.
        protocol: Protocol definition.

    Returns:
        The created VaultIndex.

    Raises:
        VaultExistsError: If vault already exists.
    """
    index_path = vault_path / "index.yaml"
    if index_path.exists():
        raise VaultExistsError(
            f"Vault already exists: {vault_path}\n"
            "Use 'scimesh vault set' to modify protocol fields.\n"
            "Use 'scimesh vault add-inclusion' or 'add-exclusion' to add criteria."
        )

    vault = VaultIndex(protocol=protocol)
    save_vault(vault_path, vault)

    # Create empty searches.yaml and papers.yaml
    save_searches(vault_path, [])
    save_papers_index(vault_path, [])

    return vault
