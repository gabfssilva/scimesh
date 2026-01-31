# scimesh/vault/__init__.py
"""Vault module for systematic literature review management."""

from scimesh.vault.models import (
    PaperEntry,
    Protocol,
    ScreeningDecision,
    ScreeningStatus,
    SearchEntry,
    SearchResults,
    VaultIndex,
    VaultStats,
)
from scimesh.vault.operations import (
    add_papers_from_search,
    add_search,
    generate_search_id,
    load_paper,
    load_papers_index,
    load_searches,
    load_vault,
    save_paper,
    save_papers_index,
    save_searches,
    save_vault,
    update_vault_stats,
)

__all__ = [
    "PaperEntry",
    "Protocol",
    "ScreeningDecision",
    "ScreeningStatus",
    "SearchEntry",
    "SearchResults",
    "VaultIndex",
    "VaultStats",
    "add_papers_from_search",
    "add_search",
    "generate_search_id",
    "load_paper",
    "load_papers_index",
    "load_searches",
    "load_vault",
    "save_paper",
    "save_papers_index",
    "save_searches",
    "save_vault",
    "update_vault_stats",
]
