"""Workspace operations extracted from CLI handlers."""

from __future__ import annotations

import sys
from pathlib import Path

from scimesh.export.paper_exporter import get_paper_path
from scimesh.models import Paper
from scimesh.workspace.models import (
    CollectionWorkspace,
    ExplorationWorkspace,
    LogEntry,
    PaperEntry,
    SearchResults,
    SLRWorkspace,
)
from scimesh.workspace.repository import (
    WorkspaceNotFoundError,
    YamlWorkspaceRepository,
)

AnyWorkspace = SLRWorkspace | ExplorationWorkspace | CollectionWorkspace


def load_or_exit(workspace_path: Path) -> AnyWorkspace:
    """Load workspace or print error and exit(1)."""
    repo = YamlWorkspaceRepository(workspace_path)
    try:
        return repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def load_strict_or_exit[W: (SLRWorkspace, ExplorationWorkspace, CollectionWorkspace)](
    workspace_path: Path,
    expected_type: type[W],
    command: str,
) -> W:
    """Load workspace; exit(1) if missing or not of expected_type."""
    workspace = load_or_exit(workspace_path)
    if not isinstance(workspace, expected_type):
        type_name = expected_type.__name__.removesuffix("Workspace").lower()
        print(f"Error: {command} only works with {type_name} workspaces", file=sys.stderr)
        sys.exit(1)
    return workspace


def ingest_papers(
    repo: YamlWorkspaceRepository,
    papers: list[Paper],
    workspace_path: Path,
    log_entry: LogEntry,
) -> int:
    """Persist new papers, append log entry with result counts, refresh stats.

    Returns count of new papers.
    """
    existing = repo.load_papers()
    existing_paths = {p.path for p in existing}

    new_entries: list[PaperEntry] = []
    for paper in papers:
        _, relative_path = get_paper_path(paper, workspace_path)
        if relative_path not in existing_paths:
            new_entries.append(
                PaperEntry(
                    path=relative_path,
                    doi=paper.doi or "",
                    title=paper.title,
                    search_ids=[log_entry.id],
                )
            )

    repo.save_papers(existing + new_entries)
    results = SearchResults(total=len(papers), unique=len(new_entries))
    repo.append_log(log_entry.model_copy(update={"results": results}))
    repo.update_stats()

    return len(new_entries)


def build_prisma_report(
    workspace: AnyWorkspace,
    papers: list[PaperEntry],
    log_entries: list[LogEntry],
    repo: YamlWorkspaceRepository,
    workspace_path: Path,
) -> str:
    """Build PRISMA flowchart + summary as a markdown string."""
    stats = workspace.stats

    flowchart = f"""```mermaid
flowchart TD
    A[Records identified<br/>n = {stats.total}] --> B[Duplicates removed<br/>n = 0]
    B --> C[Records screened<br/>n = {stats.total}]
    C --> D[Excluded<br/>n = {stats.excluded}]
    C --> E[Full-text assessed<br/>n = {stats.maybe}]
    E --> F[Excluded after full-text<br/>n = 0]
    E --> G[Included<br/>n = {stats.included}]
```"""

    included_papers = [p for p in papers if p.status == "included"]
    included_table = "| Title | DOI |\n|-------|-----|\n"
    for paper in included_papers:
        title = paper.title[:60] + "..." if len(paper.title) > 60 else paper.title
        doi = paper.doi or "-"
        included_table += f"| {title} | {doi} |\n"

    excluded_papers = [p for p in papers if p.status == "excluded"]
    excluded_table = "| Title | Reason |\n|-------|--------|\n"
    for entry in excluded_papers:
        title = entry.title[:50] + "..." if len(entry.title) > 50 else entry.title
        reason = "-"
        try:
            paper_data = repo.load_paper(entry.path)
            if paper_data.screening:
                reason = paper_data.screening.reason
        except FileNotFoundError:
            pass
        excluded_table += f"| {title} | {reason} |\n"

    searches_header = "| Query | Providers | Date | Total | Unique |"
    searches_divider = "|-------|-----------|------|-------|--------|"
    searches_table = f"{searches_header}\n{searches_divider}\n"
    for s in log_entries:
        if s.type in ("search", "snowball"):
            query_short = (s.query or "")[:40]
            if len(s.query or "") > 40:
                query_short += "..."
            date = s.executed_at.strftime("%Y-%m-%d")
            providers_str = ", ".join(s.providers)
            total = s.results.total if s.results else 0
            unique = s.results.unique if s.results else 0
            searches_table += f"| {query_short} | {providers_str} | {date} | {total} | {unique} |\n"

    inclusion_criteria = ""
    exclusion_criteria = ""
    if isinstance(workspace, SLRWorkspace):
        inclusion_criteria = f"\n**Inclusion Criteria**:\n{_format_criteria(workspace.inclusion)}\n"
        exclusion_criteria = f"\n**Exclusion Criteria**:\n{_format_criteria(workspace.exclusion)}\n"

    return f"""# Synthesis: {workspace_path.name}

## PRISMA Flow

{flowchart}

## Summary

- **Total papers**: {stats.total}
- **Included**: {stats.included}
- **Excluded**: {stats.excluded}
- **Maybe (pending)**: {stats.maybe}
- **Unscreened**: {stats.unscreened}
- **With PDF**: {stats.with_pdf}

## Searches

{searches_table}

## Included Papers

{included_table if included_papers else "No papers included yet."}

## Excluded Papers

{excluded_table if excluded_papers else "No papers excluded yet."}

## Protocol

**Research Question**: {workspace.question}
{inclusion_criteria}{exclusion_criteria}
"""


def _format_criteria(criteria: list[str]) -> str:
    if not criteria:
        return "- (none defined)"
    return "\n".join("- " + c for c in criteria)
