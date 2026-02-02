"""CLI commands for workspace management."""

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import cyclopts

from scimesh.workspace.models import (
    CollectionWorkspace,
    Constraints,
    ExplorationWorkspace,
    Framework,
    SLRWorkspace,
)
from scimesh.workspace.repository import (
    WorkspaceNotFoundError,
    YamlWorkspaceRepository,
)


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


def _format_criteria(criteria: list[str]) -> str:
    """Format criteria list for display."""
    if not criteria:
        return "- (none defined)"
    return "\n".join("- " + c for c in criteria)


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

    if type not in ("slr", "exploration", "collection"):
        print(f"Error: Invalid workspace type: {type}", file=sys.stderr)
        print("Valid options: slr, exploration, collection", file=sys.stderr)
        sys.exit(1)

    constraints = Constraints(
        databases=[db.strip() for db in databases.split(",")],
        year_range=year_range,
    )

    workspace: SLRWorkspace | ExplorationWorkspace | CollectionWorkspace

    if type == "slr":
        framework_obj = Framework(type=framework)
        workspace = SLRWorkspace(
            question=question,
            constraints=constraints,
            framework=framework_obj,
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
        str | None,
        cyclopts.Parameter(name="--question", help="Research question"),
    ] = None,
    limit: Annotated[
        int | None,
        cyclopts.Parameter(name="--limit", help="Paper limit (exploration only)"),
    ] = None,
    databases: Annotated[
        str | None,
        cyclopts.Parameter(name="--databases", help="Databases (comma-separated)"),
    ] = None,
    year_range: Annotated[
        str | None,
        cyclopts.Parameter(name="--year-range", help="Year range"),
    ] = None,
) -> None:
    """Update workspace configuration."""
    repo = YamlWorkspaceRepository(workspace_path)

    try:
        workspace = repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    updated = []

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
        repo.save(workspace)
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
    repo = YamlWorkspaceRepository(workspace_path)

    try:
        workspace = repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

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
    repo = YamlWorkspaceRepository(workspace_path)

    try:
        repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    papers = repo.load_papers()

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
    repo = YamlWorkspaceRepository(workspace_path)

    try:
        workspace = repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(workspace, ExplorationWorkspace):
        print("Error: finish command is only for exploration workspaces", file=sys.stderr)
        sys.exit(1)

    workspace = ExplorationWorkspace(
        question=workspace.question,
        constraints=workspace.constraints,
        stats=workspace.stats,
        limit=workspace.limit,
        started_at=workspace.started_at,
        finished_at=datetime.now(UTC),
    )

    repo.save(workspace)
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
    import asyncio
    import hashlib

    import streamish as st

    from scimesh import search as do_search
    from scimesh.export.paper_exporter import VaultExporter, get_paper_path
    from scimesh.models import Paper, SearchResult
    from scimesh.providers import Arxiv, OpenAlex, Scopus, SemanticScholar
    from scimesh.workspace.models import LogEntry, PaperEntry, SearchResults

    repo = YamlWorkspaceRepository(workspace_path)

    try:
        workspace = repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if providers is None:
        providers = list(workspace.constraints.databases)
    else:
        providers = [p.strip() for item in providers for p in item.split(",")]

    print(f"Searching: {query}")
    print(f"Providers: {', '.join(providers)}")

    PROVIDERS = {
        "arxiv": Arxiv,
        "openalex": OpenAlex,
        "scopus": Scopus,
        "semantic_scholar": SemanticScholar,
    }
    invalid = [p for p in providers if p not in PROVIDERS]
    if invalid:
        print(f"Error: Unknown providers: {invalid}", file=sys.stderr)
        sys.exit(1)

    provider_instances = [PROVIDERS[p]() for p in providers]

    async def _run_search() -> tuple[int, int]:
        from scimesh.cli import _create_downloader

        stream = do_search(query, providers=provider_instances, on_error="warn", dedupe=True)
        if max_results is not None:
            stream = st.take(max_results, stream)

        found_papers: list[Paper] = []
        async for paper in stream:
            found_papers.append(paper)
            print(f"  Found: {paper.title[:60]}...", file=sys.stderr)

        if not found_papers:
            print("No papers found.")
            return 0, 0

        print(f"\nExporting {len(found_papers)} papers...", file=sys.stderr)

        downloader = _create_downloader("5", scihub)
        async with downloader:
            exporter = VaultExporter(downloader=downloader, use_scihub=scihub)
            result = SearchResult(papers=found_papers)
            await exporter.export_async(result=result, output_dir=workspace_path)

        now = datetime.now(UTC)
        content = query + ",".join(sorted(providers)) + now.strftime("%Y-%m")
        search_id = hashlib.md5(content.encode()).hexdigest()[:12]

        existing_papers = repo.load_papers()
        existing_paths = {p.path for p in existing_papers}

        new_papers: list[PaperEntry] = []
        for paper in found_papers:
            _, relative_path = get_paper_path(paper, workspace_path)
            if relative_path not in existing_paths:
                new_papers.append(
                    PaperEntry(
                        path=relative_path,
                        doi=paper.doi or "",
                        title=paper.title,
                        search_ids=[search_id],
                    )
                )

        all_papers = existing_papers + new_papers
        repo.save_papers(all_papers)

        log_entry = LogEntry(
            id=search_id,
            type="search",
            query=query,
            providers=providers,
            executed_at=now,
            results=SearchResults(total=len(found_papers), unique=len(new_papers)),
            notes=notes,
        )
        repo.append_log(log_entry)

        workspace.stats.total = len(all_papers)
        repo.save(workspace)

        print(f"\nResults: {len(found_papers)} total | {len(new_papers)} unique")
        return len(found_papers), len(new_papers)

    asyncio.run(_run_search())


@workspace_app.command(name="snowball")
def workspace_snowball(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    paper_id: Annotated[str, cyclopts.Parameter(help="DOI or paper ID to snowball from")],
    direction: Annotated[
        str,
        cyclopts.Parameter(
            name=["--direction", "-d"],
            help="Citation direction: in (citing), out (references), both",
        ),
    ] = "both",
    providers: Annotated[
        list[str] | None,
        cyclopts.Parameter(name=["--provider", "-p"], help="Providers"),
    ] = None,
    max_results: Annotated[
        int,
        cyclopts.Parameter(name=["--max", "-n"], help="Max results per direction"),
    ] = 50,
    scihub: Annotated[
        bool,
        cyclopts.Parameter(name="--scihub", help="Enable Sci-Hub fallback"),
    ] = False,
) -> None:
    """Citation-based paper discovery (snowballing)."""
    import asyncio
    import hashlib

    from scimesh.export.paper_exporter import VaultExporter, get_paper_path
    from scimesh.models import Paper, SearchResult
    from scimesh.providers import OpenAlex, SemanticScholar
    from scimesh.workspace.models import LogEntry, PaperEntry, SearchResults

    repo = YamlWorkspaceRepository(workspace_path)

    try:
        workspace = repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if direction not in ("in", "out", "both"):
        print(f"Error: Invalid direction: {direction}", file=sys.stderr)
        sys.exit(1)

    if providers is None:
        providers = ["openalex", "semantic_scholar"]
    else:
        providers = [p.strip() for item in providers for p in item.split(",")]

    print(f"Snowballing from: {paper_id}")
    print(f"Direction: {direction}")
    print(f"Providers: {', '.join(providers)}")

    PROVIDERS = {
        "openalex": OpenAlex,
        "semantic_scholar": SemanticScholar,
    }

    invalid = [p for p in providers if p not in PROVIDERS]
    if invalid:
        print(f"Error: Unsupported providers: {invalid}", file=sys.stderr)
        sys.exit(1)

    async def _run_snowball() -> tuple[int, int]:
        from scimesh.cli import _create_downloader

        all_papers: list[Paper] = []

        for pname in providers:
            provider = PROVIDERS[pname]()
            try:
                async with provider:
                    count = 0
                    stream = provider.citations(
                        paper_id, direction=direction, max_results=max_results
                    )
                    async for paper in stream:
                        all_papers.append(paper)
                        count += 1
                        print(f"  [{pname}] {paper.title[:50]}...", file=sys.stderr)
                        if count >= max_results:
                            break
            except Exception as e:
                print(f"  [!] {pname}: {e}", file=sys.stderr)

        if not all_papers:
            print("No citations found.")
            return 0, 0

        print(f"\nExporting {len(all_papers)} papers...", file=sys.stderr)

        downloader = _create_downloader("5", scihub)
        async with downloader:
            exporter = VaultExporter(downloader=downloader, use_scihub=scihub)
            result = SearchResult(papers=all_papers)
            await exporter.export_async(result=result, output_dir=workspace_path)

        now = datetime.now(UTC)
        snowball_query = f"snowball:{paper_id}:{direction}"
        content = snowball_query + ",".join(sorted(providers)) + now.strftime("%Y-%m")
        search_id = hashlib.md5(content.encode()).hexdigest()[:12]

        existing_papers = repo.load_papers()
        existing_paths = {p.path for p in existing_papers}

        new_papers: list[PaperEntry] = []
        for paper in all_papers:
            _, relative_path = get_paper_path(paper, workspace_path)
            if relative_path not in existing_paths:
                new_papers.append(
                    PaperEntry(
                        path=relative_path,
                        doi=paper.doi or "",
                        title=paper.title,
                        search_ids=[search_id],
                    )
                )

        all_paper_entries = existing_papers + new_papers
        repo.save_papers(all_paper_entries)

        log_entry = LogEntry(
            id=search_id,
            type="snowball",
            query=snowball_query,
            providers=providers,
            executed_at=now,
            results=SearchResults(total=len(all_papers), unique=len(new_papers)),
            seed_doi=paper_id,
            direction=direction,
        )
        repo.append_log(log_entry)

        workspace.stats.total = len(all_paper_entries)
        repo.save(workspace)

        print(f"\nResults: {len(all_papers)} total | {len(new_papers)} unique")
        return len(all_papers), len(new_papers)

    asyncio.run(_run_snowball())


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
    repo = YamlWorkspaceRepository(workspace_path)

    try:
        repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    papers = repo.load_papers()
    paper_paths = {entry.path: entry for entry in papers}

    updated = 0
    errors = 0

    def process_papers(papers_args: list[str], status: str) -> None:
        nonlocal updated, errors
        for paper_id, reason in _parse_screening_args(papers_args):
            matched_path = None
            for path in paper_paths:
                if path == paper_id or paper_id in path:
                    matched_path = path
                    break

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
        process_papers(include, "included")
    if exclude:
        process_papers(exclude, "excluded")
    if maybe:
        process_papers(maybe, "maybe")

    if updated > 0:
        repo.update_stats()

    print(f"\nUpdated: {updated} | Errors: {errors}")


@workspace_app.command(name="export")
def workspace_export(
    workspace_path: Annotated[Path, cyclopts.Parameter(help="Path to workspace")],
    output: Annotated[
        Path | None,
        cyclopts.Parameter(name=["--output", "-o"], help="Output file"),
    ] = None,
    format: Annotated[
        str,
        cyclopts.Parameter(name=["--format", "-f"], help="Format: bibtex, ris, csv, json, yaml"),
    ] = "bibtex",
    status: Annotated[
        str | None,
        cyclopts.Parameter(name="--status", help="Filter by status"),
    ] = None,
) -> None:
    """Export papers to various formats."""
    import yaml as yaml_lib

    from scimesh.export import get_exporter
    from scimesh.models import Author, Paper, SearchResult

    repo = YamlWorkspaceRepository(workspace_path)

    try:
        repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    papers = repo.load_papers()

    if status:
        valid_statuses = ["included", "excluded", "maybe", "unscreened"]
        if status not in valid_statuses:
            print(f"Error: Invalid status: {status}", file=sys.stderr)
            print(f"Valid options: {', '.join(valid_statuses)}", file=sys.stderr)
            sys.exit(1)
        papers = [p for p in papers if p.status == status]

    if not papers:
        print("No papers to export.", file=sys.stderr)
        return

    full_papers: list[Paper] = []
    for entry in papers:
        try:
            paper_index = repo.load_paper(entry.path)
            paper = Paper(
                title=paper_index.title,
                authors=tuple(Author(name=a) for a in paper_index.authors),
                year=paper_index.year,
                doi=paper_index.doi,
                abstract=paper_index.abstract,
                journal=paper_index.journal,
                url=next(iter(paper_index.urls.values()), None) if paper_index.urls else None,
                source=paper_index.sources[0] if paper_index.sources else "workspace",
            )
            full_papers.append(paper)
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
    else:
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
    repo = YamlWorkspaceRepository(workspace_path)

    try:
        workspace = repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(workspace, SLRWorkspace):
        print("Error: add-inclusion only works with SLR workspaces", file=sys.stderr)
        sys.exit(1)

    existing = set(workspace.inclusion)
    new_criteria = [c for c in criteria if c not in existing]

    if new_criteria:
        workspace.inclusion = list(existing | set(new_criteria))
        repo.save(workspace)
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
    repo = YamlWorkspaceRepository(workspace_path)

    try:
        workspace = repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(workspace, SLRWorkspace):
        print("Error: add-exclusion only works with SLR workspaces", file=sys.stderr)
        sys.exit(1)

    existing = set(workspace.exclusion)
    new_criteria = [c for c in criteria if c not in existing]

    if new_criteria:
        workspace.exclusion = list(existing | set(new_criteria))
        repo.save(workspace)
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
    repo = YamlWorkspaceRepository(workspace_path)

    try:
        repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    stats = repo.update_stats()

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
        Path | None,
        cyclopts.Parameter(name=["--output", "-o"], help="Output markdown file"),
    ] = None,
) -> None:
    """Generate PRISMA flowchart and summary tables."""
    repo = YamlWorkspaceRepository(workspace_path)

    try:
        workspace = repo.load()
    except WorkspaceNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    stats = workspace.stats
    papers = repo.load_papers()
    log_entries = repo.load_log()

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

    content = f"""# Synthesis: {workspace_path.name}

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

    if output:
        output.write_text(content, encoding="utf-8")
        print(f"PRISMA synthesis written to {output}")
    else:
        print(content)
