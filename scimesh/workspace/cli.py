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
    from scimesh.export.vault import VaultExporter, get_paper_path
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
