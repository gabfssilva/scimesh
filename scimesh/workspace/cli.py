"""CLI commands for workspace management."""

from __future__ import annotations

import asyncio
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, get_args

import cyclopts
import streamish as st
import yaml as yaml_lib

from scimesh import search as do_search
from scimesh.download import create_downloader
from scimesh.export import get_exporter
from scimesh.export.paper_exporter import VaultExporter
from scimesh.models import Author, Paper, SearchResult
from scimesh.providers import Arxiv, OpenAlex, Scopus, SemanticScholar
from scimesh.workspace.models import (
    CollectionWorkspace,
    Constraints,
    ExplorationWorkspace,
    Framework,
    LogEntry,
    PaperStatus,
    SLRWorkspace,
)
from scimesh.workspace.operations import (
    build_prisma_report,
    ingest_papers,
    load_or_exit,
    load_strict_or_exit,
)
from scimesh.workspace.repository import (
    WorkspaceExistsError,
    YamlWorkspaceRepository,
)

PROVIDERS = {
    "arxiv": Arxiv,
    "openalex": OpenAlex,
    "scopus": Scopus,
    "semantic_scholar": SemanticScholar,
}
SNOWBALL_PROVIDERS = {
    "openalex": OpenAlex,
    "semantic_scholar": SemanticScholar,
}
WORKSPACE_TYPES = ("slr", "exploration", "collection")
Direction = Literal["in", "out", "both"]
PAPER_STATUSES = get_args(PaperStatus)


def _parse_screening_args(args: list[str]) -> list[tuple[str, str]]:
    """Parse paper_id:reason pairs from arguments."""
    results = []
    i = 0
    while i < len(args):
        item = args[i]
        if ":" in item:
            parts = item.split(":", 1)
            paper_id = parts[0]
            reason = parts[1].strip() if len(parts) > 1 else ""
            if not reason and i + 1 < len(args) and ":" not in args[i + 1]:
                reason = args[i + 1]
                i += 1
            results.append((paper_id, reason))
        i += 1
    return results


def _search_id(query: str, providers: list[str], now: datetime) -> str:
    content = query + ",".join(sorted(providers)) + now.strftime("%Y-%m")
    return hashlib.md5(content.encode()).hexdigest()[:12]


workspace_app = cyclopts.App(
    name="workspace",
    help="Manage paper workspaces (SLR, exploration, collection).",
)


@workspace_app.command(name="init")
def workspace_init(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to create workspace")],
    type: Annotated[
        str, cyclopts.Parameter(name="--type", help="Workspace type: slr, exploration, collection")
    ] = "exploration",
    question: Annotated[
        str, cyclopts.Parameter(name="--question", help="Research question or topic")
    ] = "",
    framework: Annotated[
        str, cyclopts.Parameter(name="--framework", help="Framework: pico, spider, custom")
    ] = "custom",
    limit: Annotated[
        int | None, cyclopts.Parameter(name="--limit", help="Paper limit (exploration only)")
    ] = None,
    databases: Annotated[
        str, cyclopts.Parameter(name="--databases", help="Databases (comma-separated)")
    ] = "openalex,semantic_scholar",
    year_range: Annotated[
        str | None, cyclopts.Parameter(name="--year-range", help="Year range")
    ] = None,
) -> None:
    """Initialize a new workspace."""
    repo = YamlWorkspaceRepository(workspace_path)

    if repo.exists():
        print(f"Error: Workspace already exists at {workspace_path}", file=sys.stderr)
        sys.exit(1)

    if type not in WORKSPACE_TYPES:
        print(f"Error: Invalid workspace type: {type}", file=sys.stderr)
        print(f"Valid options: {', '.join(WORKSPACE_TYPES)}", file=sys.stderr)
        sys.exit(1)

    constraints = Constraints(
        databases=[db.strip() for db in databases.split(",")],
        year_range=year_range,
    )

    workspace: SLRWorkspace | ExplorationWorkspace | CollectionWorkspace
    if type == "slr":
        workspace = SLRWorkspace(
            question=question,
            constraints=constraints,
            framework=Framework(type=framework),
        )
    elif type == "exploration":
        workspace = ExplorationWorkspace(
            question=question,
            constraints=constraints,
            limit=limit,
            started_at=datetime.now(UTC),
        )
    else:
        workspace = CollectionWorkspace(
            question=question,
            constraints=constraints,
        )

    repo.save(workspace)
    repo.save_log([])
    repo.save_papers([])

    print(f"Workspace created at: {workspace_path}")


@workspace_app.command(name="set")
def workspace_set(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    question: Annotated[
        str | None, cyclopts.Parameter(name="--question", help="Research question")
    ] = None,
    limit: Annotated[
        int | None, cyclopts.Parameter(name="--limit", help="Paper limit (exploration only)")
    ] = None,
    databases: Annotated[
        str | None, cyclopts.Parameter(name="--databases", help="Databases (comma-separated)")
    ] = None,
    year_range: Annotated[
        str | None, cyclopts.Parameter(name="--year-range", help="Year range")
    ] = None,
) -> None:
    """Update workspace configuration."""
    workspace = load_or_exit(workspace_path)
    updated: list[str] = []

    if question is not None:
        workspace.question = question
        updated.append(f"question: {question}")

    if databases is not None:
        workspace.constraints.databases = [db.strip() for db in databases.split(",")]
        updated.append(f"databases: {databases}")

    if year_range is not None:
        workspace.constraints.year_range = year_range if year_range else None
        updated.append(f"year_range: {year_range}")

    if limit is not None and isinstance(workspace, ExplorationWorkspace):
        workspace.limit = limit
        updated.append(f"limit: {limit}")

    if updated:
        YamlWorkspaceRepository(workspace_path).save(workspace)
        print("Updated:")
        for u in updated:
            print(f"  {u}")
    else:
        print("Nothing to update. Use --help for options.")


@workspace_app.command(name="stats")
def workspace_stats(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
) -> None:
    """Show workspace info and statistics."""
    workspace = load_or_exit(workspace_path)

    print(f"Type: {workspace.type}")
    print(f"Question: {workspace.question}")
    print()

    if isinstance(workspace, SLRWorkspace):
        print(f"Framework: {workspace.framework.type}")
        if workspace.framework.fields:
            for key, value in workspace.framework.fields.items():
                print(f"  {key}: {value}")
        print()

    if workspace.constraints.databases:
        print(f"Databases: {', '.join(workspace.constraints.databases)}")
    if workspace.constraints.year_range:
        print(f"Year range: {workspace.constraints.year_range}")
    print()

    if isinstance(workspace, ExplorationWorkspace):
        if workspace.limit:
            print(f"Limit: {workspace.limit}")
        if workspace.started_at:
            print(f"Started: {workspace.started_at.strftime('%Y-%m-%d %H:%M')}")
        if workspace.finished_at:
            print(f"Finished: {workspace.finished_at.strftime('%Y-%m-%d %H:%M')}")
        print()

    stats = workspace.stats
    print(f"Total papers: {stats.total}")
    if stats.total > 0:
        print(f"  with_pdf:   {stats.with_pdf}")
        print(f"  included:   {stats.included}")
        print(f"  excluded:   {stats.excluded}")
        print(f"  maybe:      {stats.maybe}")
        print(f"  unscreened: {stats.unscreened}")


@workspace_app.command(name="list")
def workspace_list(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    status: Annotated[
        str | None, cyclopts.Parameter(name="--status", help="Filter by status")
    ] = None,
) -> None:
    """List papers in workspace."""
    load_or_exit(workspace_path)
    papers = YamlWorkspaceRepository(workspace_path).load_papers()

    if status:
        papers = [p for p in papers if p.status == status]

    if not papers:
        print("No papers found.")
        return

    print(f"{'Path':<45} {'Status':<12} Title")
    print("-" * 100)
    for paper in papers:
        title = paper.title[:40] + "..." if len(paper.title) > 40 else paper.title
        print(f"{paper.path:<45} {paper.status:<12} {title}")

    print(f"\nTotal: {len(papers)} papers")


@workspace_app.command(name="finish")
def workspace_finish(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
) -> None:
    """Mark exploration workspace as finished."""
    workspace = load_strict_or_exit(workspace_path, ExplorationWorkspace, "finish")
    workspace.finished_at = datetime.now(UTC)
    YamlWorkspaceRepository(workspace_path).save(workspace)
    print(f"Workspace finished: {workspace_path}")


@workspace_app.command(name="search")
def workspace_search(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    query: Annotated[str, cyclopts.Parameter(help="Scopus-style query string")],
    providers: Annotated[
        list[str] | None, cyclopts.Parameter(name=["--provider", "-p"], help="Providers")
    ] = None,
    max_results: Annotated[
        int | None, cyclopts.Parameter(name=["--max", "-n"], help="Max results")
    ] = None,
    notes: Annotated[
        str | None, cyclopts.Parameter(name="--notes", help="Notes for this search")
    ] = None,
    scihub: Annotated[
        bool, cyclopts.Parameter(name="--scihub", help="Enable Sci-Hub fallback")
    ] = False,
) -> None:
    """Search and add papers to workspace."""
    workspace = load_or_exit(workspace_path)
    repo = YamlWorkspaceRepository(workspace_path)

    if providers is None:
        providers = list(workspace.constraints.databases)
    else:
        providers = [p.strip() for item in providers for p in item.split(",")]

    invalid = [p for p in providers if p not in PROVIDERS]
    if invalid:
        print(f"Error: Unknown providers: {invalid}", file=sys.stderr)
        sys.exit(1)

    print(f"Searching: {query}")
    print(f"Providers: {', '.join(providers)}")

    provider_instances = [PROVIDERS[p]() for p in providers]

    async def _run() -> None:
        stream = do_search(query, providers=provider_instances, on_error="warn", dedupe=True)
        if max_results is not None:
            stream = st.take(max_results, stream)

        found: list[Paper] = []
        async for paper in stream:
            found.append(paper)
            print(f"  Found: {paper.title[:60]}...", file=sys.stderr)

        if not found:
            print("No papers found.")
            return

        print(f"\nExporting {len(found)} papers...", file=sys.stderr)

        downloader = create_downloader("5", scihub)
        async with downloader:
            exporter = VaultExporter(downloader=downloader, use_scihub=scihub)
            await exporter.export_async(
                result=SearchResult(papers=found), output_dir=workspace_path
            )

        now = datetime.now(UTC)
        new_count = ingest_papers(
            repo,
            found,
            workspace_path,
            LogEntry(
                id=_search_id(query, providers, now),
                type="search",
                query=query,
                providers=providers,
                executed_at=now,
                notes=notes,
            ),
        )
        print(f"\nResults: {len(found)} total | {new_count} unique")

    asyncio.run(_run())


@workspace_app.command(name="snowball")
def workspace_snowball(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    paper_id: Annotated[str, cyclopts.Parameter(help="DOI or paper ID to snowball from")],
    direction: Annotated[
        Direction,
        cyclopts.Parameter(
            name=["--direction", "-d"],
            help="Citation direction: in (citing), out (references), both",
        ),
    ] = "both",
    providers: Annotated[
        list[str] | None, cyclopts.Parameter(name=["--provider", "-p"], help="Providers")
    ] = None,
    max_results: Annotated[
        int, cyclopts.Parameter(name=["--max", "-n"], help="Max results per direction")
    ] = 50,
    scihub: Annotated[
        bool, cyclopts.Parameter(name="--scihub", help="Enable Sci-Hub fallback")
    ] = False,
) -> None:
    """Citation-based paper discovery (snowballing)."""
    load_or_exit(workspace_path)
    repo = YamlWorkspaceRepository(workspace_path)

    if providers is None:
        providers = ["openalex", "semantic_scholar"]
    else:
        providers = [p.strip() for item in providers for p in item.split(",")]

    invalid = [p for p in providers if p not in SNOWBALL_PROVIDERS]
    if invalid:
        print(f"Error: Unsupported providers: {invalid}", file=sys.stderr)
        sys.exit(1)

    print(f"Snowballing from: {paper_id}")
    print(f"Direction: {direction}")
    print(f"Providers: {', '.join(providers)}")

    async def _run() -> None:
        found: list[Paper] = []
        for pname in providers:
            provider = SNOWBALL_PROVIDERS[pname]()
            try:
                async with provider:
                    count = 0
                    stream = provider.citations(
                        paper_id, direction=direction, max_results=max_results
                    )
                    async for paper in stream:
                        found.append(paper)
                        count += 1
                        print(f"  [{pname}] {paper.title[:50]}...", file=sys.stderr)
                        if count >= max_results:
                            break
            except Exception as e:
                print(f"  [!] {pname}: {e}", file=sys.stderr)

        if not found:
            print("No citations found.")
            return

        print(f"\nExporting {len(found)} papers...", file=sys.stderr)

        downloader = create_downloader("5", scihub)
        async with downloader:
            exporter = VaultExporter(downloader=downloader, use_scihub=scihub)
            await exporter.export_async(
                result=SearchResult(papers=found), output_dir=workspace_path
            )

        now = datetime.now(UTC)
        snowball_query = f"snowball:{paper_id}:{direction}"
        new_count = ingest_papers(
            repo,
            found,
            workspace_path,
            LogEntry(
                id=_search_id(snowball_query, providers, now),
                type="snowball",
                query=snowball_query,
                providers=providers,
                executed_at=now,
                seed_doi=paper_id,
                direction=direction,
            ),
        )
        print(f"\nResults: {len(found)} total | {new_count} unique")

    asyncio.run(_run())


@workspace_app.command(name="screen")
def workspace_screen(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    include: Annotated[
        list[str] | None,
        cyclopts.Parameter(name="--include", help="Papers to include (paper_id:reason)"),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        cyclopts.Parameter(name="--exclude", help="Papers to exclude (paper_id:reason)"),
    ] = None,
    maybe: Annotated[
        list[str] | None,
        cyclopts.Parameter(name="--maybe", help="Papers marked maybe (paper_id:reason)"),
    ] = None,
) -> None:
    """Set screening status for papers."""
    load_or_exit(workspace_path)
    repo = YamlWorkspaceRepository(workspace_path)
    papers = repo.load_papers()
    paper_paths = {entry.path: entry for entry in papers}

    updated = 0
    errors = 0

    def process(args: list[str], status: PaperStatus) -> None:
        nonlocal updated, errors
        for paper_id, reason in _parse_screening_args(args):
            matched_path = next((p for p in paper_paths if p == paper_id or paper_id in p), None)
            if not matched_path:
                print(f"  [!] Paper not found: {paper_id}", file=sys.stderr)
                errors += 1
                continue
            try:
                repo.set_paper_screening(matched_path, status, reason)
                print(f"  [{status}] {matched_path}")
                updated += 1
            except FileNotFoundError:
                print(f"  [!] Paper directory not found: {matched_path}", file=sys.stderr)
                errors += 1

    if include:
        process(include, "included")
    if exclude:
        process(exclude, "excluded")
    if maybe:
        process(maybe, "maybe")

    if updated > 0:
        repo.update_stats()

    print(f"\nUpdated: {updated} | Errors: {errors}")


@workspace_app.command(name="export")
def workspace_export(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    output: Annotated[
        Path | None, cyclopts.Parameter(name=["--output", "-o"], help="Output file")
    ] = None,
    format: Annotated[
        str,
        cyclopts.Parameter(name=["--format", "-f"], help="Format: bibtex, ris, csv, json, yaml"),
    ] = "bibtex",
    status: Annotated[
        str | None, cyclopts.Parameter(name="--status", help="Filter by status")
    ] = None,
) -> None:
    """Export papers to various formats."""
    load_or_exit(workspace_path)
    repo = YamlWorkspaceRepository(workspace_path)
    papers = repo.load_papers()

    if status:
        if status not in PAPER_STATUSES:
            print(f"Error: Invalid status: {status}", file=sys.stderr)
            print(f"Valid options: {', '.join(PAPER_STATUSES)}", file=sys.stderr)
            sys.exit(1)
        papers = [p for p in papers if p.status == status]

    if not papers:
        print("No papers to export.", file=sys.stderr)
        return

    full_papers: list[Paper] = []
    for entry in papers:
        try:
            paper_index = repo.load_paper(entry.path)
            full_papers.append(
                Paper(
                    title=paper_index.title,
                    authors=tuple(Author(name=a) for a in paper_index.authors),
                    year=paper_index.year,
                    doi=paper_index.doi,
                    abstract=paper_index.abstract,
                    journal=paper_index.journal,
                    url=next(iter(paper_index.urls.values()), None) if paper_index.urls else None,
                    source=paper_index.sources[0] if paper_index.sources else "workspace",
                )
            )
        except FileNotFoundError:
            print(f"  [!] Skipping missing paper: {entry.path}", file=sys.stderr)

    result = SearchResult(papers=full_papers)

    if format in ("yaml", "yml"):
        data = [
            {
                "title": p.title,
                "authors": [a.name for a in p.authors],
                "year": p.year,
                "doi": p.doi,
            }
            for p in full_papers
        ]
        content = yaml_lib.dump(data, default_flow_style=False, allow_unicode=True)
        if output:
            output.write_text(content, encoding="utf-8")
            print(f"Exported {len(full_papers)} papers to {output}")
        else:
            print(content)
        return

    try:
        exporter = get_exporter(format)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if output:
        exporter.export(result, output)
        print(f"Exported {len(full_papers)} papers to {output}")
    else:
        print(exporter.to_string(result))


@workspace_app.command(name="add-inclusion")
def workspace_add_inclusion(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    criteria: Annotated[list[str], cyclopts.Parameter(help="Inclusion criteria to add")],
) -> None:
    """Add inclusion criteria (SLR workspaces only)."""
    workspace = load_strict_or_exit(workspace_path, SLRWorkspace, "add-inclusion")
    existing = set(workspace.inclusion)
    new_criteria = [c for c in criteria if c not in existing]

    if new_criteria:
        workspace.inclusion = list(existing | set(new_criteria))
        YamlWorkspaceRepository(workspace_path).save(workspace)
        print(f"Added {len(new_criteria)} inclusion criteria:")
        for c in new_criteria:
            print(f"  + {c}")
    else:
        print("All criteria already exist.")


@workspace_app.command(name="add-exclusion")
def workspace_add_exclusion(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    criteria: Annotated[list[str], cyclopts.Parameter(help="Exclusion criteria to add")],
) -> None:
    """Add exclusion criteria (SLR workspaces only)."""
    workspace = load_strict_or_exit(workspace_path, SLRWorkspace, "add-exclusion")
    existing = set(workspace.exclusion)
    new_criteria = [c for c in criteria if c not in existing]

    if new_criteria:
        workspace.exclusion = list(existing | set(new_criteria))
        YamlWorkspaceRepository(workspace_path).save(workspace)
        print(f"Added {len(new_criteria)} exclusion criteria:")
        for c in new_criteria:
            print(f"  + {c}")
    else:
        print("All criteria already exist.")


@workspace_app.command(name="update-stats")
def workspace_update_stats(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
) -> None:
    """Recalculate workspace statistics from papers."""
    load_or_exit(workspace_path)
    stats = YamlWorkspaceRepository(workspace_path).update_stats()

    print("Statistics updated:")
    print(f"  Total: {stats.total}")
    print(f"  With PDF: {stats.with_pdf}")
    print(f"  Included: {stats.included}")
    print(f"  Excluded: {stats.excluded}")
    print(f"  Maybe: {stats.maybe}")
    print(f"  Unscreened: {stats.unscreened}")


@workspace_app.command(name="prisma")
def workspace_prisma(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    output: Annotated[
        Path | None, cyclopts.Parameter(name=["--output", "-o"], help="Output markdown file")
    ] = None,
) -> None:
    """Generate PRISMA flowchart and summary tables."""
    workspace = load_or_exit(workspace_path)
    repo = YamlWorkspaceRepository(workspace_path)
    content = build_prisma_report(
        workspace, repo.load_papers(), repo.load_log(), repo, workspace_path
    )

    if output:
        output.write_text(content, encoding="utf-8")
        print(f"PRISMA synthesis written to {output}")
    else:
        print(content)


__all__ = ["workspace_app", "WorkspaceExistsError"]
