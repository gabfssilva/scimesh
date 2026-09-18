from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Annotated

import cyclopts
import streamish as st

from scimesh.api import Direction, Scimesh
from scimesh.cache import Cache
from scimesh.export import ALL_FORMATS, get_exporter
from scimesh.export.tree import TreeExporter
from scimesh.models import Paper, SearchResult
from scimesh.providers import REGISTRY
from scimesh.search import OnError

app = cyclopts.App(
    name="scimesh",
    help="Scientific paper search across multiple providers.",
)

cache_app = cyclopts.App(name="cache", help="Inspect and maintain the local cache.")
app.command(cache_app)


def _setup_logging(log_level: str | None) -> None:
    if log_level:
        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.WARNING),
            format="%(levelname)s %(name)s: %(message)s",
        )


def _parse_providers(values: list[str]) -> list[str]:
    names = [p.strip() for item in values for p in item.split(",")]
    invalid = [p for p in names if p not in REGISTRY]
    if invalid:
        print(f"Error: Unknown providers: {invalid}", file=sys.stderr)
        print(f"Available: {list(REGISTRY)}", file=sys.stderr)
        sys.exit(1)
    return names


def _resolve_format(format: str, output: Path | None) -> str:
    if format == "tree" and output is None and not sys.stdout.isatty():
        format = "json"
    if format not in ALL_FORMATS:
        print(f"Error: Unknown export format: {format}", file=sys.stderr)
        sys.exit(1)
    return format


def _emit(papers: list[Paper], format: str, output: Path | None, totals: dict[str, int]) -> None:
    result = SearchResult(papers=papers, total_by_provider=totals)
    exporter = get_exporter(format)

    if output:
        exporter.export(result, output)
        print(f"Exported {len(papers)} papers to {output}")
    elif format == "tree":
        for i, paper in enumerate(papers):
            if i > 0:
                print()
            print(TreeExporter().format_paper(paper))
    else:
        print(exporter.to_string(result))

    print(f"\nTotal: {len(papers)} papers", file=sys.stderr)


@app.command(name="search")
def search(
    query: Annotated[str, cyclopts.Parameter(help="Scopus-style query string")],
    providers: Annotated[
        list[str],
        cyclopts.Parameter(
            name=["--provider", "-p"],
            help="Providers to search (arxiv, openalex, scopus, semantic_scholar)",
        ),
    ] = ["openalex"],
    output: Annotated[
        Path | None,
        cyclopts.Parameter(name=["--output", "-o"], help="Output file path"),
    ] = None,
    format: Annotated[
        str,
        cyclopts.Parameter(
            name=["--format", "-f"], help="Output format: tree, csv, json, bibtex, ris"
        ),
    ] = "tree",
    max_results: Annotated[
        int,
        cyclopts.Parameter(name=["--max", "-n"], help="Maximum total results"),
    ] = 100,
    on_error: Annotated[
        OnError,
        cyclopts.Parameter(name="--on-error", help="Error handling: fail, warn, ignore"),
    ] = "warn",
    no_dedupe: Annotated[
        bool,
        cyclopts.Parameter(name="--no-dedupe", help="Disable deduplication"),
    ] = False,
    refresh: Annotated[
        bool,
        cyclopts.Parameter(name="--refresh", help="Ignore cached API responses"),
    ] = False,
    log_level: Annotated[
        str | None,
        cyclopts.Parameter(name="--log-level", help="Log level: debug, info, warning, error"),
    ] = None,
) -> None:
    """Search for scientific papers across multiple providers."""
    _setup_logging(log_level)
    names = _parse_providers(providers)
    format = _resolve_format(format, output)
    streaming = format == "tree" and output is None

    async def run() -> tuple[list[Paper], dict[str, int]]:
        papers: list[Paper] = []
        totals: dict[str, int] = {}
        async with Scimesh(names, on_error=on_error, dedupe=not no_dedupe, refresh=refresh) as sm:
            async for paper in st.take(max_results, sm.search(query)):
                if streaming:
                    if papers:
                        print()
                    print(TreeExporter().format_paper(paper))
                papers.append(paper)
                totals[paper.source] = totals.get(paper.source, 0) + 1
        return papers, totals

    papers, totals = asyncio.run(run())

    if streaming:
        print(f"\nTotal: {len(papers)} papers", file=sys.stderr)
        for name, count in totals.items():
            print(f"  {name}: {count}", file=sys.stderr)
        return

    _emit(papers, format, output, totals)


@app.command(name="get")
def get(
    paper_id: Annotated[str, cyclopts.Parameter(help="DOI or provider-specific paper ID")],
    providers: Annotated[
        list[str],
        cyclopts.Parameter(name=["--provider", "-p"], help="Providers to query"),
    ] = ["openalex", "semantic_scholar"],
    output: Annotated[
        Path | None,
        cyclopts.Parameter(name=["--output", "-o"], help="Output file path"),
    ] = None,
    format: Annotated[
        str,
        cyclopts.Parameter(
            name=["--format", "-f"], help="Output format: tree, csv, json, bibtex, ris"
        ),
    ] = "tree",
    refresh: Annotated[
        bool,
        cyclopts.Parameter(name="--refresh", help="Ignore cached API responses"),
    ] = False,
) -> None:
    """Fetch a specific paper by DOI or ID, merging what each provider knows."""
    names = _parse_providers(providers)
    format = _resolve_format(format, output)

    async def run() -> Paper | None:
        async with Scimesh(names, refresh=refresh) as sm:
            return await sm.get(paper_id)

    paper = asyncio.run(run())

    if paper is None:
        print(f"Error: Paper not found: {paper_id}", file=sys.stderr)
        sys.exit(1)

    _emit([paper], format, output, {paper.source: 1})


@app.command(name="citations")
def citations(
    paper_id: Annotated[str, cyclopts.Parameter(help="DOI or provider-specific paper ID")],
    direction: Annotated[
        Direction,
        cyclopts.Parameter(
            name=["--direction", "-d"],
            help="in (citing this paper), out (cited by this paper), both",
        ),
    ] = "both",
    providers: Annotated[
        list[str],
        cyclopts.Parameter(name=["--provider", "-p"], help="Providers to query"),
    ] = ["openalex"],
    output: Annotated[
        Path | None,
        cyclopts.Parameter(name=["--output", "-o"], help="Output file path"),
    ] = None,
    format: Annotated[
        str,
        cyclopts.Parameter(
            name=["--format", "-f"], help="Output format: tree, csv, json, bibtex, ris"
        ),
    ] = "tree",
    max_results: Annotated[
        int,
        cyclopts.Parameter(name=["--max", "-n"], help="Maximum number of results"),
    ] = 100,
    no_dedupe: Annotated[
        bool,
        cyclopts.Parameter(name="--no-dedupe", help="Disable deduplication"),
    ] = False,
    refresh: Annotated[
        bool,
        cyclopts.Parameter(name="--refresh", help="Ignore cached API responses"),
    ] = False,
) -> None:
    """Get papers citing or cited by a specific paper."""
    names = _parse_providers(providers)
    format = _resolve_format(format, output)

    async def run() -> list[Paper]:
        async with Scimesh(names, dedupe=not no_dedupe, refresh=refresh) as sm:
            return [
                paper
                async for paper in sm.citations(
                    paper_id, direction=direction, max_results=max_results
                )
            ]

    papers = asyncio.run(run())

    if not papers:
        print(f"No citations found for: {paper_id}", file=sys.stderr)
        sys.exit(0)

    totals: dict[str, int] = {}
    for paper in papers:
        totals[paper.source] = totals.get(paper.source, 0) + 1

    _emit(papers, format, output, totals)


def _extract_arxiv_doi_from_url(url: str | None) -> str | None:
    """Extract arXiv DOI from an arXiv URL.

    Example: https://arxiv.org/abs/1908.06954v2 -> 10.48550/arXiv.1908.06954
    """
    if not url:
        return None
    match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", url)
    return f"10.48550/arXiv.{match.group(1)}" if match else None


def _parse_ids_from_stdin() -> list[str]:
    """Parse paper ids from JSON piped via stdin ({"papers": [{"doi": ...}]})."""
    try:
        data = json.load(sys.stdin)
        papers = data.get("papers", [])
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []

    ids: list[str] = []
    for paper in papers:
        doi = paper.get("doi") or _extract_arxiv_doi_from_url(paper.get("url"))
        if doi:
            ids.append(doi)
    return ids


def _parse_ids_from_file(filepath: Path) -> list[str]:
    """Parse paper ids from a file, one per line, ignoring comments."""
    return [
        line.strip()
        for line in filepath.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _collect_ids(paper_id: str | None, from_file: Path | None) -> list[str]:
    if from_file is not None:
        if not from_file.exists():
            print(f"Error: File not found: {from_file}", file=sys.stderr)
            sys.exit(1)
        ids = _parse_ids_from_file(from_file)
    elif paper_id is not None:
        ids = [paper_id]
    elif not sys.stdin.isatty():
        ids = _parse_ids_from_stdin()
    else:
        ids = []

    if not ids:
        print(
            "Error: No papers provided. Use a positional arg, --from file, or pipe JSON.",
            file=sys.stderr,
        )
        sys.exit(1)

    return ids


def _output_name(key: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", key) + ".pdf"


@app.command(name="download")
def download(
    paper_id: Annotated[str | None, cyclopts.Parameter(help="DOI to download")] = None,
    from_file: Annotated[
        Path | None,
        cyclopts.Parameter(name=["--from", "-f"], help="File with DOIs (one per line)"),
    ] = None,
    output: Annotated[
        Path,
        cyclopts.Parameter(name=["--output", "-o"], help="Output directory for PDFs"),
    ] = Path("."),
    extract: Annotated[
        bool,
        cyclopts.Parameter(name="--extract", help="Also extract and cache the text"),
    ] = False,
    scihub: Annotated[
        bool,
        cyclopts.Parameter(name="--scihub", help="Enable Sci-Hub fallback (use at your own risk)"),
    ] = False,
    concurrency: Annotated[
        int,
        cyclopts.Parameter(name="--concurrency", help="Concurrent downloads"),
    ] = 5,
    host_concurrency: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--host-concurrency",
            help="Concurrency: '3' (all hosts) or 'arxiv.org=2,api.unpaywall.org=3' (per-host)",
        ),
    ] = None,
    log_level: Annotated[
        str | None,
        cyclopts.Parameter(name="--log-level", help="Log level: debug, info, warning, error"),
    ] = None,
) -> None:
    """Download papers by DOI into a directory, caching each one once."""
    _setup_logging(log_level)
    ids = _collect_ids(paper_id, from_file)
    output.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(ids)} papers to {output}/")

    async def run() -> tuple[int, int]:
        succeeded = failed = 0
        async with Scimesh([], scihub=scihub, host_concurrency=host_concurrency) as sm:
            async for fetch in sm.fetch_many(ids, concurrency=concurrency, extract=extract):
                if fetch.success:
                    assert fetch.path is not None
                    name = _output_name(fetch.key)
                    (output / name).write_bytes(fetch.path.read_bytes())
                    print(f"  ✓ {name} ({fetch.source})")
                    succeeded += 1
                else:
                    print(f"  ✗ {fetch.key} - {fetch.error}")
                    failed += 1
        return succeeded, failed

    succeeded, failed = asyncio.run(run())
    print(f"Downloaded: {succeeded}/{succeeded + failed} | Failed: {failed}")


@app.command(name="text")
def text(
    paper_id: Annotated[str, cyclopts.Parameter(help="DOI or arXiv id")],
    output: Annotated[
        Path | None,
        cyclopts.Parameter(name=["--output", "-o"], help="Output file path"),
    ] = None,
    scihub: Annotated[
        bool,
        cyclopts.Parameter(name="--scihub", help="Enable Sci-Hub fallback (use at your own risk)"),
    ] = False,
    host_concurrency: Annotated[
        str | None,
        cyclopts.Parameter(name="--host-concurrency", help="Concurrency limit for downloads"),
    ] = None,
    log_level: Annotated[
        str | None,
        cyclopts.Parameter(name="--log-level", help="Log level: debug, info, warning, error"),
    ] = None,
) -> None:
    """Print a paper's text as markdown, extracting it once and caching it."""
    _setup_logging(log_level)

    async def run() -> str | None:
        async with Scimesh([], scihub=scihub, host_concurrency=host_concurrency) as sm:
            return await sm.text(paper_id)

    markdown = asyncio.run(run())

    if markdown is None:
        print(f"Error: No text available for: {paper_id}", file=sys.stderr)
        sys.exit(1)

    if output:
        output.write_text(markdown)
        print(f"Wrote {len(markdown)} characters to {output}")
    else:
        print(markdown)


@cache_app.command(name="stats")
def cache_stats() -> None:
    """Show what the cache holds."""
    with Cache() as cache:
        stats = cache.stats()
        print(f"Path:      {cache.root}")
        print(f"PDFs:      {stats.documents} ({stats.bytes / 1_000_000:.1f} MB)")
        print(f"Texts:     {stats.texts}")
        print(f"Responses: {stats.responses}")
        print(f"Failures:  {stats.failures}")


@cache_app.command(name="search")
def cache_search(
    term: Annotated[str, cyclopts.Parameter(help="FTS5 query over cached text")],
    max_results: Annotated[
        int,
        cyclopts.Parameter(name=["--max", "-n"], help="Maximum number of results"),
    ] = 100,
) -> None:
    """Search the text of papers already in the cache."""
    with Cache() as cache:
        keys = cache.search(term, limit=max_results)

    for key in keys:
        print(key)
    print(f"\nTotal: {len(keys)} papers", file=sys.stderr)


@cache_app.command(name="gc")
def cache_gc() -> None:
    """Drop dangling rows, delete unreferenced files, expire stale API responses."""
    with Cache() as cache:
        report = cache.gc()
    print(
        f"Dropped rows: {report.dropped_rows} | "
        f"Deleted files: {report.deleted_files} | "
        f"Expired responses: {report.expired_responses}"
    )


@cache_app.command(name="clear")
def cache_clear() -> None:
    """Remove every cached PDF, text and failure."""
    with Cache() as cache:
        stats = cache.stats()
        cache.clear()
    print(
        f"Cleared {stats.documents} PDFs, {stats.texts} texts and {stats.responses} API responses"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
