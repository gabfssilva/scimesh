# scimesh/vault/cli.py
"""CLI commands for vault management."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated

import cyclopts
import yaml

from scimesh.vault.models import (
    PaperEntry,
    Protocol,
    ScreeningStatus,
    SearchEntry,
    SearchResults,
    VaultIndex,
)
from scimesh.vault.operations import (
    VaultExistsError,
    VaultNotFoundError,
    add_papers_from_search,
    add_search,
    generate_search_id,
    init_vault,
    load_paper,
    load_papers_index,
    load_searches,
    load_vault,
    save_vault,
    set_paper_screening,
    update_vault_stats,
)

vault_app = cyclopts.App(
    name="vault",
    help="Systematic literature review vault management.",
)


@vault_app.command(name="init")
def vault_init(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to create vault")],
    question: Annotated[str, cyclopts.Parameter(name="--question", help="Research question")] = "",
    population: Annotated[
        str, cyclopts.Parameter(name="--population", help="PICO: Population")
    ] = "",
    intervention: Annotated[
        str, cyclopts.Parameter(name="--intervention", help="PICO: Intervention")
    ] = "",
    comparison: Annotated[
        str, cyclopts.Parameter(name="--comparison", help="PICO: Comparison")
    ] = "",
    outcome: Annotated[str, cyclopts.Parameter(name="--outcome", help="PICO: Outcome")] = "",
    inclusion: Annotated[
        list[str] | None,
        cyclopts.Parameter(name="--inclusion", help="Inclusion criteria (repeat for multiple)"),
    ] = None,
    exclusion: Annotated[
        list[str] | None,
        cyclopts.Parameter(name="--exclusion", help="Exclusion criteria (repeat for multiple)"),
    ] = None,
    databases: Annotated[
        str, cyclopts.Parameter(name="--databases", help="Databases (comma-separated)")
    ] = "arxiv,openalex,semantic_scholar",
    year_range: Annotated[
        str, cyclopts.Parameter(name="--year-range", help="Year range (e.g., 2020-2024)")
    ] = "",
) -> None:
    """Initialize a new SLR vault with protocol."""
    protocol = Protocol(
        question=question,
        population=population,
        intervention=intervention,
        comparison=comparison,
        outcome=outcome,
        inclusion=tuple(inclusion) if inclusion else (),
        exclusion=tuple(exclusion) if exclusion else (),
        databases=tuple(db.strip() for db in databases.split(",")),
        year_range=year_range,
    )

    try:
        init_vault(vault_path, protocol)
        print(f"Vault created at: {vault_path}")
    except VaultExistsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


@vault_app.command(name="set")
def vault_set(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
    question: Annotated[
        str | None, cyclopts.Parameter(name="--question", help="Research question")
    ] = None,
    population: Annotated[
        str | None, cyclopts.Parameter(name="--population", help="Population")
    ] = None,
    intervention: Annotated[
        str | None, cyclopts.Parameter(name="--intervention", help="Intervention")
    ] = None,
    comparison: Annotated[
        str | None, cyclopts.Parameter(name="--comparison", help="Comparison")
    ] = None,
    outcome: Annotated[str | None, cyclopts.Parameter(name="--outcome", help="Outcome")] = None,
    year_range: Annotated[
        str | None, cyclopts.Parameter(name="--year-range", help="Year range")
    ] = None,
    databases: Annotated[
        str | None, cyclopts.Parameter(name="--databases", help="Databases (comma-separated)")
    ] = None,
) -> None:
    """Modify protocol fields."""
    try:
        vault = load_vault(vault_path)
    except VaultNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Build updated protocol
    new_protocol = Protocol(
        question=question if question is not None else vault.protocol.question,
        population=population if population is not None else vault.protocol.population,
        intervention=intervention if intervention is not None else vault.protocol.intervention,
        comparison=comparison if comparison is not None else vault.protocol.comparison,
        outcome=outcome if outcome is not None else vault.protocol.outcome,
        inclusion=vault.protocol.inclusion,
        exclusion=vault.protocol.exclusion,
        databases=tuple(db.strip() for db in databases.split(","))
        if databases
        else vault.protocol.databases,
        year_range=year_range if year_range is not None else vault.protocol.year_range,
    )

    updated_vault = VaultIndex(
        protocol=new_protocol,
        stats=vault.stats,
    )

    save_vault(vault_path, updated_vault)
    print(f"Protocol updated: {vault_path}")


@vault_app.command(name="add-inclusion")
def vault_add_inclusion(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
    criteria: Annotated[list[str], cyclopts.Parameter(help="Inclusion criteria to add")],
) -> None:
    """Add inclusion criteria to protocol."""
    try:
        vault = load_vault(vault_path)
    except VaultNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    new_inclusion = vault.protocol.inclusion + tuple(criteria)
    new_protocol = Protocol(
        question=vault.protocol.question,
        population=vault.protocol.population,
        intervention=vault.protocol.intervention,
        comparison=vault.protocol.comparison,
        outcome=vault.protocol.outcome,
        inclusion=new_inclusion,
        exclusion=vault.protocol.exclusion,
        databases=vault.protocol.databases,
        year_range=vault.protocol.year_range,
    )

    updated_vault = VaultIndex(
        protocol=new_protocol,
        stats=vault.stats,
    )

    save_vault(vault_path, updated_vault)
    print(f"Added {len(criteria)} inclusion criteria")


@vault_app.command(name="add-exclusion")
def vault_add_exclusion(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
    criteria: Annotated[list[str], cyclopts.Parameter(help="Exclusion criteria to add")],
) -> None:
    """Add exclusion criteria to protocol."""
    try:
        vault = load_vault(vault_path)
    except VaultNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    new_exclusion = vault.protocol.exclusion + tuple(criteria)
    new_protocol = Protocol(
        question=vault.protocol.question,
        population=vault.protocol.population,
        intervention=vault.protocol.intervention,
        comparison=vault.protocol.comparison,
        outcome=vault.protocol.outcome,
        inclusion=vault.protocol.inclusion,
        exclusion=new_exclusion,
        databases=vault.protocol.databases,
        year_range=vault.protocol.year_range,
    )

    updated_vault = VaultIndex(
        protocol=new_protocol,
        stats=vault.stats,
    )

    save_vault(vault_path, updated_vault)
    print(f"Added {len(criteria)} exclusion criteria")


def _format_criteria(criteria: tuple[str, ...]) -> str:
    """Format criteria list for PRISMA output."""
    if not criteria:
        return "- (none defined)"
    return "\n".join("- " + c for c in criteria)


def _parse_screening_args(args: list[str]) -> list[tuple[str, str]]:
    """Parse paper_id:reason pairs from arguments.

    Supports:
      - paper_id:reason (colon-separated)
      - paper_id: reason (colon with space)
      - paper_id (no reason)
    """
    results: list[tuple[str, str]] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if ":" in arg:
            # Split on first colon
            paper_id, reason = arg.split(":", 1)
            results.append((paper_id.strip(), reason.strip()))
        else:
            # No colon - check if next arg is the reason
            paper_id = arg
            reason = ""
            results.append((paper_id, reason))
        i += 1
    return results


@vault_app.command(name="screen")
def vault_screen(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
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
    # Verify vault exists
    if not (vault_path / "index.yaml").exists():
        print(f"Error: Vault not found: {vault_path}", file=sys.stderr)
        sys.exit(1)

    # Build paper path lookup from papers.yaml
    papers_list = load_papers_index(vault_path)
    paper_paths = {entry.path: entry for entry in papers_list}

    updated = 0
    errors = 0

    def process_papers(papers: list[str], status: ScreeningStatus) -> None:
        nonlocal updated, errors
        for item in _parse_screening_args(papers):
            paper_id, reason = item
            # Try to find paper by path or partial match
            matched_path = None
            for path in paper_paths:
                if path == paper_id or paper_id in path:
                    matched_path = path
                    break

            if not matched_path:
                print(f"  [!] Paper not found: {paper_id}", file=sys.stderr)
                errors += 1
                continue

            paper_path = vault_path / matched_path
            try:
                set_paper_screening(vault_path, paper_path, status, reason)
                print(f"  [{status.value}] {matched_path}")
                updated += 1
            except FileNotFoundError:
                print(f"  [!] Paper directory not found: {matched_path}", file=sys.stderr)
                errors += 1

    if include:
        process_papers(include, ScreeningStatus.INCLUDED)
    if exclude:
        process_papers(exclude, ScreeningStatus.EXCLUDED)
    if maybe:
        process_papers(maybe, ScreeningStatus.MAYBE)

    if updated > 0:
        # Update vault stats
        update_vault_stats(vault_path)

    print(f"\nUpdated: {updated} | Errors: {errors}")


@vault_app.command(name="list")
def vault_list(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
    status: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--status", help="Filter by status (included, excluded, maybe, unscreened)"
        ),
    ] = None,
    format: Annotated[
        str,
        cyclopts.Parameter(name="--format", help="Output format: table, paths, json"),
    ] = "table",
) -> None:
    """List papers in vault."""
    # Verify vault exists
    if not (vault_path / "index.yaml").exists():
        print(f"Error: Vault not found: {vault_path}", file=sys.stderr)
        sys.exit(1)

    # Load papers from papers.yaml
    papers = load_papers_index(vault_path)
    if status:
        try:
            filter_status = ScreeningStatus(status)
            papers = [p for p in papers if p.status == filter_status]
        except ValueError:
            print(f"Error: Invalid status: {status}", file=sys.stderr)
            print("Valid options: included, excluded, maybe, unscreened", file=sys.stderr)
            sys.exit(1)

    if not papers:
        print("No papers found.")
        return

    if format == "paths":
        for paper in papers:
            print(paper.path)
    elif format == "json":
        import json

        data = [p.to_dict() for p in papers]
        print(json.dumps(data, indent=2))
    else:
        # Table format
        print(f"{'ID':<40} {'Year':>4} {'Status':<10} Title")
        print("-" * 100)
        for paper in papers:
            # Extract year from path (format: year-author-slug)
            year = paper.path.split("-")[0] if "-" in paper.path else "?"
            title = paper.title[:45] + "..." if len(paper.title) > 45 else paper.title
            print(f"{paper.path:<40} {year:>4} {paper.status.value:<10} {title}")

    print(f"\nTotal: {len(papers)} papers")


@vault_app.command(name="stats")
def vault_stats(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
    refresh: Annotated[
        bool,
        cyclopts.Parameter(name="--refresh", help="Refresh stats from paper directories"),
    ] = False,
) -> None:
    """Show screening statistics."""
    try:
        if refresh:
            stats = update_vault_stats(vault_path)
        else:
            vault = load_vault(vault_path)
            stats = vault.stats
    except VaultNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Total papers: {stats.total}")
    print()

    if stats.total > 0:
        pct_included = (stats.included / stats.total) * 100
        pct_excluded = (stats.excluded / stats.total) * 100
        pct_maybe = (stats.maybe / stats.total) * 100
        pct_unscreened = (stats.unscreened / stats.total) * 100

        print(f"  included:   {stats.included:>4} ({pct_included:>5.1f}%)")
        print(f"  excluded:   {stats.excluded:>4} ({pct_excluded:>5.1f}%)")
        print(f"  maybe:      {stats.maybe:>4} ({pct_maybe:>5.1f}%)")
        print(f"  unscreened: {stats.unscreened:>4} ({pct_unscreened:>5.1f}%)")
        print()

        screened = stats.included + stats.excluded + stats.maybe
        progress = (screened / stats.total) * 100
        print(f"Progress: {progress:.0f}%")

        if stats.with_pdf > 0:
            print(f"With PDF: {stats.with_pdf}")


@vault_app.command(name="export")
def vault_export(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
    output: Annotated[
        Path | None,
        cyclopts.Parameter(name=["--output", "-o"], help="Output file"),
    ] = None,
    format: Annotated[
        str,
        cyclopts.Parameter(
            name=["--format", "-f"], help="Output format: bibtex, ris, csv, json, yaml"
        ),
    ] = "bibtex",
    status: Annotated[
        str | None,
        cyclopts.Parameter(name="--status", help="Filter by status"),
    ] = None,
) -> None:
    """Export papers to various formats."""
    # Verify vault exists
    if not (vault_path / "index.yaml").exists():
        print(f"Error: Vault not found: {vault_path}", file=sys.stderr)
        sys.exit(1)

    # Load papers from papers.yaml
    papers = load_papers_index(vault_path)
    if status:
        try:
            filter_status = ScreeningStatus(status)
            papers = [p for p in papers if p.status == filter_status]
        except ValueError:
            print(f"Error: Invalid status: {status}", file=sys.stderr)
            sys.exit(1)

    if not papers:
        print("No papers to export.", file=sys.stderr)
        return

    # Load full paper data
    from scimesh.models import Author, Paper, SearchResult

    full_papers: list[Paper] = []
    for entry in papers:
        paper_path = vault_path / entry.path
        try:
            data = load_paper(paper_path)
            paper = Paper(
                title=data.get("title", ""),
                authors=tuple(Author(name=a) for a in data.get("authors", [])),
                year=data.get("year", 0),
                doi=data.get("doi"),
                abstract=data.get("abstract"),
                journal=data.get("journal"),
                url=next(iter(data.get("urls", {}).values()), None),
                source=data.get("sources", ["vault"])[0] if data.get("sources") else "vault",
            )
            full_papers.append(paper)
        except FileNotFoundError:
            print(f"  [!] Skipping missing paper: {entry.path}", file=sys.stderr)

    result = SearchResult(papers=full_papers)

    # Export
    from scimesh.export import get_exporter

    if format in ("yaml", "yml"):
        # YAML export (not in standard exporters)
        data = [
            {
                "title": p.title,
                "authors": [a.name for a in p.authors],
                "year": p.year,
                "doi": p.doi,
            }
            for p in full_papers
        ]
        content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
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


@vault_app.command(name="prisma")
def vault_prisma(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
    output: Annotated[
        Path | None,
        cyclopts.Parameter(name=["--output", "-o"], help="Output markdown file"),
    ] = None,
) -> None:
    """Generate PRISMA flowchart and summary tables."""
    try:
        vault = load_vault(vault_path)
    except VaultNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    stats = vault.stats
    papers = load_papers_index(vault_path)
    searches = load_searches(vault_path)

    # Build PRISMA flowchart
    flowchart = f"""```mermaid
flowchart TD
    A[Records identified<br/>n = {stats.total}] --> B[Duplicates removed<br/>n = 0]
    B --> C[Records screened<br/>n = {stats.total}]
    C --> D[Excluded<br/>n = {stats.excluded}]
    C --> E[Full-text assessed<br/>n = {stats.maybe}]
    E --> F[Excluded after full-text<br/>n = 0]
    E --> G[Included<br/>n = {stats.included}]
```"""

    # Build included papers table
    included_papers = [p for p in papers if p.status == ScreeningStatus.INCLUDED]
    included_table = "| Title | Year | DOI |\n|-------|------|-----|\n"
    for paper in included_papers:
        year = paper.path.split("-")[0] if "-" in paper.path else "?"
        title = paper.title[:60] + "..." if len(paper.title) > 60 else paper.title
        doi = paper.doi or "-"
        included_table += f"| {title} | {year} | {doi} |\n"

    # Build excluded papers table
    excluded_papers = [p for p in papers if p.status == ScreeningStatus.EXCLUDED]
    excluded_table = "| Title | Year | Reason |\n|-------|------|--------|\n"
    for entry in excluded_papers:
        year = entry.path.split("-")[0] if "-" in entry.path else "?"
        title = entry.title[:50] + "..." if len(entry.title) > 50 else entry.title
        # Get reason from paper index
        paper_path = vault_path / entry.path
        reason = "-"
        try:
            data = load_paper(paper_path)
            reason = data.get("screening", {}).get("reason", "-")
        except FileNotFoundError:
            pass
        excluded_table += f"| {title} | {year} | {reason} |\n"

    # Build searches table
    searches_table = (
        "| Query | Providers | Date | Total | Unique |\n"
        "|-------|-----------|------|-------|--------|\n"
    )
    for s in searches:
        query_short = s.query[:40] + "..." if len(s.query) > 40 else s.query
        date = s.executed_at.strftime("%Y-%m-%d")
        providers_str = ", ".join(s.providers)
        total, unique = s.results.total, s.results.unique
        searches_table += f"| {query_short} | {providers_str} | {date} | {total} | {unique} |\n"

    # Compose full document
    content = f"""# Synthesis: {vault_path.name}

## PRISMA Flow

{flowchart}

## Summary Statistics

- **Total papers**: {stats.total}
- **Included**: {stats.included}
- **Excluded**: {stats.excluded}
- **Maybe (pending full-text)**: {stats.maybe}
- **Unscreened**: {stats.unscreened}

## Searches ({len(searches)})

{searches_table}

## Included Papers ({stats.included})

{included_table}

## Excluded Papers ({stats.excluded})

{excluded_table}

## Protocol

**Research Question**: {vault.protocol.question}

**Inclusion Criteria**:
{_format_criteria(vault.protocol.inclusion)}

**Exclusion Criteria**:
{_format_criteria(vault.protocol.exclusion)}
"""

    if output:
        output.write_text(content, encoding="utf-8")
        print(f"PRISMA synthesis written to {output}")
    else:
        print(content)


@vault_app.command(name="search")
def vault_search(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
    query: Annotated[str, cyclopts.Parameter(help="Scopus-style query string")],
    providers: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            name=["--provider", "-p"],
            help="Providers (defaults to protocol databases)",
        ),
    ] = None,
    max_results: Annotated[
        int | None,
        cyclopts.Parameter(name=["--max", "-n"], help="Maximum total results"),
    ] = None,
    scihub: Annotated[
        bool,
        cyclopts.Parameter(name="--scihub", help="Enable Sci-Hub fallback for PDFs"),
    ] = False,
) -> None:
    """Search and add papers to vault."""
    try:
        vault = load_vault(vault_path)
    except VaultNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Initialize with: scimesh vault init <path>", file=sys.stderr)
        sys.exit(1)

    # Use protocol databases if not specified
    if providers is None:
        providers = list(vault.protocol.databases)
    else:
        providers = [p.strip() for item in providers for p in item.split(",")]

    print(f"Searching: {query}")
    print(f"Providers: {', '.join(providers)}")
    print()

    # Import search functionality
    from scimesh import search as do_search
    from scimesh import take
    from scimesh.export.vault import VaultExporter
    from scimesh.models import Paper
    from scimesh.providers import Arxiv, CrossRef, OpenAlex, Scopus, SemanticScholar

    PROVIDERS = {
        "arxiv": Arxiv,
        "openalex": OpenAlex,
        "scopus": Scopus,
        "semantic_scholar": SemanticScholar,
        "crossref": CrossRef,
    }

    # Validate providers
    invalid = [p for p in providers if p not in PROVIDERS]
    if invalid:
        print(f"Error: Unknown providers: {invalid}", file=sys.stderr)
        sys.exit(1)

    # Create provider instances
    provider_instances = [PROVIDERS[p]() for p in providers]

    async def _run_search() -> tuple[int, int]:
        from scimesh.cli import _create_downloader
        from scimesh.export.vault import get_paper_path

        stream = do_search(
            query,
            providers=provider_instances,
            on_error="warn",
            dedupe=True,
            stream=True,
        )
        if max_results is not None:
            stream = take(max_results, stream)

        found_papers: list[Paper] = []
        async for paper in stream:
            found_papers.append(paper)
            print(f"  Found: {paper.title[:60]}...", file=sys.stderr)

        if not found_papers:
            print("No papers found.")
            return 0, 0

        print(f"\nExporting {len(found_papers)} papers to {vault_path}/", file=sys.stderr)

        downloader = _create_downloader("5", scihub)
        async with downloader:
            exporter = VaultExporter(downloader=downloader, use_scihub=scihub)

            from scimesh.models import SearchResult

            result = SearchResult(papers=found_papers)
            export_stats = await exporter.export_async(
                result=result,
                output_dir=vault_path,
            )

        # Generate search ID and track papers
        search_id = generate_search_id(query, providers)

        # Build PaperEntry list from found papers
        paper_entries = [
            PaperEntry(
                path=get_paper_path(p, vault_path)[1],
                doi=p.doi or "",
                title=p.title,
                status=ScreeningStatus.UNSCREENED,
                search_ids=(),  # Will be set by add_papers_from_search
            )
            for p in found_papers
        ]

        # Add papers to papers.yaml (handles dedup and search_id assignment)
        total, unique = add_papers_from_search(vault_path, paper_entries, search_id)

        # Record the search
        from datetime import UTC, datetime

        search_entry = SearchEntry(
            id=search_id,
            query=query,
            providers=tuple(providers),
            executed_at=datetime.now(UTC),
            results=SearchResults(total=total, unique=unique),
        )
        add_search(vault_path, search_entry)

        print(
            f"\nResults: {total} total | {unique} unique",
            file=sys.stderr,
        )
        if export_stats.with_pdf > 0:
            print(f"With PDF: {export_stats.with_pdf}", file=sys.stderr)

        # Update vault stats
        update_vault_stats(vault_path)

        return total, unique

    asyncio.run(_run_search())


@vault_app.command(name="snowball")
def vault_snowball(
    vault_path: Annotated[Path, cyclopts.Parameter(help="Path to vault")],
    paper_id: Annotated[str, cyclopts.Parameter(help="DOI or paper ID to snowball from")],
    direction: Annotated[
        str,
        cyclopts.Parameter(
            name=["--direction", "-d"],
            help="Citation direction: in (citing), out (references), both",
        ),
    ] = "both",
    providers: Annotated[
        list[str],
        cyclopts.Parameter(
            name=["--provider", "-p"],
            help="Providers (openalex, semantic_scholar)",
        ),
    ] = ["openalex", "semantic_scholar"],
    max_results: Annotated[
        int,
        cyclopts.Parameter(name=["--max", "-n"], help="Maximum results per direction"),
    ] = 50,
    scihub: Annotated[
        bool,
        cyclopts.Parameter(name="--scihub", help="Enable Sci-Hub fallback for PDFs"),
    ] = False,
) -> None:
    """Citation-based paper discovery (snowballing)."""
    try:
        load_vault(vault_path)  # Verify vault exists
    except VaultNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate direction
    if direction not in ("in", "out", "both"):
        print(f"Error: Invalid direction: {direction}", file=sys.stderr)
        print("Valid options: in (forward citations), out (references), both", file=sys.stderr)
        sys.exit(1)

    # Normalize providers
    providers = [p.strip() for item in providers for p in item.split(",")]

    print(f"Snowballing from: {paper_id}")
    print(f"Direction: {direction}")
    print(f"Providers: {', '.join(providers)}")
    print()

    from scimesh.providers import OpenAlex, SemanticScholar

    CITATIONS_PROVIDERS = {
        "openalex": OpenAlex,
        "semantic_scholar": SemanticScholar,
    }

    # Validate providers
    invalid = [p for p in providers if p not in CITATIONS_PROVIDERS]
    if invalid:
        print(f"Error: Unsupported providers for citations: {invalid}", file=sys.stderr)
        print(f"Available: {list(CITATIONS_PROVIDERS.keys())}", file=sys.stderr)
        sys.exit(1)

    async def _run_snowball() -> tuple[int, int]:
        from scimesh.cli import _create_downloader
        from scimesh.export.vault import VaultExporter, get_paper_path
        from scimesh.models import Paper, SearchResult

        all_papers: list[Paper] = []

        for pname in providers:
            provider = CITATIONS_PROVIDERS[pname]()
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

        print(f"\nExporting {len(all_papers)} papers to {vault_path}/", file=sys.stderr)

        downloader = _create_downloader("5", scihub)
        async with downloader:
            exporter = VaultExporter(downloader=downloader, use_scihub=scihub)
            result = SearchResult(papers=all_papers)
            export_stats = await exporter.export_async(
                result=result,
                output_dir=vault_path,
            )

        # Generate search ID for snowball
        snowball_query = f"snowball:{paper_id}:{direction}"
        search_id = generate_search_id(snowball_query, providers)

        # Build PaperEntry list from found papers
        paper_entries = [
            PaperEntry(
                path=get_paper_path(p, vault_path)[1],
                doi=p.doi or "",
                title=p.title,
                status=ScreeningStatus.UNSCREENED,
                search_ids=(),
            )
            for p in all_papers
        ]

        # Add papers to papers.yaml
        total, unique = add_papers_from_search(vault_path, paper_entries, search_id)

        # Record the search
        from datetime import UTC, datetime

        search_entry = SearchEntry(
            id=search_id,
            query=snowball_query,
            providers=tuple(providers),
            executed_at=datetime.now(UTC),
            results=SearchResults(total=total, unique=unique),
            type="snowball",
            seed_doi=paper_id,
            direction=direction,
        )
        add_search(vault_path, search_entry)

        print(
            f"\nResults: {total} total | {unique} unique",
            file=sys.stderr,
        )
        if export_stats.with_pdf > 0:
            print(f"With PDF: {export_stats.with_pdf}", file=sys.stderr)

        # Update vault stats
        update_vault_stats(vault_path)

        return total, unique

    asyncio.run(_run_snowball())
