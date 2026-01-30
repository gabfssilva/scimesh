# scimesh/cli.py
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts

from scimesh import search as do_search
from scimesh import take
from scimesh.download import download_papers
from scimesh.export import get_exporter
from scimesh.export.tree import TreeExporter
from scimesh.models import Paper, SearchResult, merge_papers
from scimesh.providers import Arxiv, CrossRef, OpenAlex, Scopus, SemanticScholar
from scimesh.providers.base import Provider

if TYPE_CHECKING:
    from scimesh.download import FallbackDownloader

app = cyclopts.App(
    name="scimesh",
    help="Scientific paper search across multiple providers.",
)


def _setup_logging(log_level: str | None) -> None:
    """Configure logging based on log level."""
    if log_level:
        level = getattr(logging, log_level.upper(), logging.WARNING)
        logging.basicConfig(
            level=level,
            format="%(levelname)s %(name)s: %(message)s",
        )


PROVIDERS = {
    "arxiv": Arxiv,
    "openalex": OpenAlex,
    "scopus": Scopus,
    "semantic_scholar": SemanticScholar,
    "crossref": CrossRef,
}

# Providers that support the get() method
GET_PROVIDERS = {
    "arxiv": Arxiv,
    "openalex": OpenAlex,
    "scopus": Scopus,
    "semantic_scholar": SemanticScholar,
    "crossref": CrossRef,
}

# Providers that support the citations() method
CITATIONS_PROVIDERS = {
    "openalex": OpenAlex,
    "scopus": Scopus,
    "semantic_scholar": SemanticScholar,
}


def _parse_host_concurrency(value: str | None) -> tuple[dict[str, int] | None, int | None]:  # noqa: C901
    """Parse host concurrency string into dict and/or default.

    Args:
        value: Either an integer string ("3") for default limit, or
            per-host config like "arxiv.org=2,api.unpaywall.org=3".
            Can also combine: "3,arxiv.org=2" (default 3, arxiv 2).

    Returns:
        Tuple of (per-host limits dict, default limit).
    """
    if not value:
        return None, None

    # Try parsing as plain integer (default for all hosts)
    try:
        return None, int(value)
    except ValueError:
        pass

    # Parse as host=limit pairs
    result: dict[str, int] = {}
    default: int | None = None
    for part in value.split(","):
        part = part.strip()
        if "=" in part:
            host, limit = part.split("=", 1)
            try:
                result[host.strip()] = int(limit.strip())
            except ValueError:
                pass
        else:
            # Plain number is default
            try:
                default = int(part)
            except ValueError:
                pass

    return (result if result else None), default


def _create_downloader(
    host_concurrency: str | None = None,
    use_scihub: bool = False,
) -> FallbackDownloader:
    """Create a FallbackDownloader with OpenAccess and optionally SciHub."""
    from scimesh.download import (
        Downloader,
        FallbackDownloader,
        HostSemaphores,
        OpenAccessDownloader,
        SciHubDownloader,
    )

    host_limits, default_limit = _parse_host_concurrency(host_concurrency)
    host_semaphores = None
    if host_limits or default_limit:
        host_semaphores = HostSemaphores(host_limits, default=default_limit)

    downloaders: list[Downloader] = [OpenAccessDownloader(host_semaphores=host_semaphores)]
    if use_scihub:
        downloaders.append(SciHubDownloader(host_semaphores=host_semaphores))

    return FallbackDownloader(*downloaders)


async def _stream_search(
    query: str,
    provider_instances: list[Provider],
    on_error: str,
    tree_exporter: TreeExporter,
    max_results: int | None = None,
    dedupe: bool = True,
) -> int:
    """Stream search results, printing each paper as it arrives."""
    count = 0

    stream = do_search(
        query,
        providers=provider_instances,
        on_error=on_error,  # type: ignore
        dedupe=dedupe,
        stream=True,
    )
    if max_results is not None:
        stream = take(max_results, stream)

    async for paper in stream:
        if count > 0:
            print()  # Blank line between papers
        print(tree_exporter.format_paper(paper))
        count += 1

    return count


@app.command(name="search")
def search(
    query: Annotated[str, cyclopts.Parameter(help="Scopus-style query string")],
    providers: Annotated[
        list[str],
        cyclopts.Parameter(
            name=["--provider", "-p"],
            help="Providers to search (arxiv, openalex, scopus, semantic_scholar, crossref)",
        ),
    ] = ["openalex"],
    output: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--output", "-o"], help="Output file path (required for vault format)"
        ),
    ] = None,
    format: Annotated[
        str,
        cyclopts.Parameter(
            name=["--format", "-f"], help="Output format: tree, csv, json, bibtex, ris, vault"
        ),
    ] = "tree",
    max_results: Annotated[
        int | None,
        cyclopts.Parameter(name=["--max", "-n"], help="Maximum total results"),
    ] = None,
    on_error: Annotated[
        str,
        cyclopts.Parameter(name="--on-error", help="Error handling: fail, warn, ignore"),
    ] = "warn",
    no_dedupe: Annotated[
        bool,
        cyclopts.Parameter(name="--no-dedupe", help="Disable deduplication"),
    ] = False,
    local_fulltext_indexing: Annotated[
        bool,
        cyclopts.Parameter(
            name="--local-fulltext-indexing",
            help="Download and index PDFs for fulltext search (no native fulltext)",
        ),
    ] = False,
    scihub: Annotated[
        bool,
        cyclopts.Parameter(
            name="--scihub",
            help="Enable Sci-Hub fallback for PDF downloads (requires --local-fulltext-indexing)",
        ),
    ] = False,
    host_concurrency: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--host-concurrency",
            help="Concurrency: '3' (all hosts) or 'arxiv.org=2,api.unpaywall.org=3' (per-host)",
        ),
    ] = "5",
    log_level: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--log-level",
            help="Log level: debug, info, warning, error",
        ),
    ] = None,
) -> None:
    """Search for scientific papers across multiple providers."""
    _setup_logging(log_level)

    # Normalize providers (support comma-separated values)
    providers = [p.strip() for item in providers for p in item.split(",")]

    # Validate providers
    invalid = [p for p in providers if p not in PROVIDERS]
    if invalid:
        print(f"Error: Unknown providers: {invalid}", file=sys.stderr)
        print(f"Available: {list(PROVIDERS.keys())}", file=sys.stderr)
        sys.exit(1)

    # Auto-switch to JSON when piping (for download command compatibility)
    if format == "tree" and output is None and not sys.stdout.isatty():
        format = "json"

    # Validate format early
    try:
        exporter = get_exporter(format)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Special validation for vault format
    if format == "vault" and output is None:
        print("Error: --output is required for vault format", file=sys.stderr)
        sys.exit(1)

    # Create provider instances
    provider_instances: list[Provider] = []
    downloader = _create_downloader(host_concurrency, scihub) if local_fulltext_indexing else None

    for p in providers:
        if downloader and p in ("crossref", "semantic_scholar"):
            provider_instances.append(PROVIDERS[p](downloader=downloader))
        else:
            provider_instances.append(PROVIDERS[p]())

    # Use streaming for tree format without output file (only in terminal)
    if format == "tree" and output is None:
        count = asyncio.run(
            _stream_search(
                query,
                provider_instances,
                on_error,
                TreeExporter(),
                max_results,
                dedupe=not no_dedupe,
            )
        )
        print(f"\nTotal: {count} papers", file=sys.stderr)
        return

    # Vault format has special handling
    if format == "vault":
        from scimesh.export.vault import VaultExporter

        async def _export_vault() -> int:
            downloader = _create_downloader(host_concurrency, scihub)

            stream = do_search(
                query,
                providers=provider_instances,
                on_error=on_error,  # type: ignore
                dedupe=not no_dedupe,
                stream=True,
            )
            if max_results is not None:
                stream = take(max_results, stream)

            papers: list[Paper] = []
            async for paper in stream:
                papers.append(paper)
                print(f"  Found: {paper.title[:50]}...", file=sys.stderr)

            result = SearchResult(papers=papers)

            print(f"\nExporting {len(papers)} papers to {output}/", file=sys.stderr)

            # Use async with to initialize the downloader
            async with downloader:
                exporter = VaultExporter(downloader=downloader, use_scihub=scihub)
                stats = await exporter.export_async(
                    result=result,
                    output_dir=output,
                    query=query,
                    providers=providers,
                )

            print(
                f"Exported: {stats.total} | Skipped: {stats.skipped} | With PDF: {stats.with_pdf}",
                file=sys.stderr,
            )
            return stats.total

        asyncio.run(_export_vault())
        return

    # Non-streaming path for other formats or file output
    async def _collect_with_limit() -> SearchResult:
        stream = do_search(
            query,
            providers=provider_instances,
            on_error=on_error,  # type: ignore
            dedupe=not no_dedupe,
            stream=True,
        )
        if max_results is not None:
            stream = take(max_results, stream)

        papers: list[Paper] = []
        totals: dict[str, int] = {}
        async for paper in stream:
            papers.append(paper)
            totals[paper.source] = totals.get(paper.source, 0) + 1
        return SearchResult(papers=papers, total_by_provider=totals)

    result = asyncio.run(_collect_with_limit())

    # Export results
    if output:
        exporter.export(result, output)
        print(f"Exported {len(result.papers)} papers to {output}")
    else:
        print(exporter.to_string(result))

    # Summary
    print(f"\nTotal: {len(result.papers)} papers", file=sys.stderr)
    for pname, count in result.total_by_provider.items():
        print(f"  {pname}: {count}", file=sys.stderr)


def _extract_arxiv_doi_from_url(url: str | None) -> str | None:
    """Extract arXiv DOI from arXiv URL.

    Example: https://arxiv.org/abs/1908.06954v2 -> 10.48550/arXiv.1908.06954
    """
    if not url:
        return None
    import re

    match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", url)
    if match:
        return f"10.48550/arXiv.{match.group(1)}"
    return None


def _parse_dois_from_stdin() -> list[str]:  # noqa: C901
    """Parse DOIs from JSON piped via stdin.

    Expects JSON with structure: {"papers": [{"doi": "...", "url": "..."}, ...]}
    Falls back to constructing arXiv DOIs from URLs when DOI is missing.
    """
    try:
        data = json.load(sys.stdin)
        papers = data.get("papers", [])
        dois: list[str] = []
        for p in papers:
            doi = p.get("doi")
            if doi:
                dois.append(doi)
            else:
                # Try to extract arXiv DOI from URL
                arxiv_doi = _extract_arxiv_doi_from_url(p.get("url"))
                if arxiv_doi:
                    dois.append(arxiv_doi)
        return dois
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _parse_dois_from_file(filepath: Path) -> list[str]:
    """Parse DOIs from a file, one DOI per line."""
    dois: list[str] = []
    with filepath.open() as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                dois.append(line)
    return dois


async def _run_downloads(
    dois: list[str],
    output_dir: Path,
    use_scihub: bool = False,
    host_concurrency: str | None = None,
) -> tuple[int, int]:
    """Run downloads and print progress. Returns (success_count, fail_count)."""
    downloader = _create_downloader(host_concurrency, use_scihub)

    success_count = 0
    fail_count = 0

    async for result in download_papers(dois, output_dir, downloaders=[downloader]):
        if result.success:
            print(f"  \u2713 {result.filename} ({result.source})")
            success_count += 1
        else:
            error_msg = result.error or "not found"
            # Extract short error message
            if "All downloaders failed" in error_msg:
                error_msg = "not found"
            print(f"  \u2717 {result.doi} - {error_msg}")
            fail_count += 1

    return success_count, fail_count


@app.command(name="download")
def download(
    doi: Annotated[
        str | None,
        cyclopts.Parameter(help="DOI to download"),
    ] = None,
    from_file: Annotated[
        Path | None,
        cyclopts.Parameter(name=["--from", "-f"], help="File with DOIs (one per line)"),
    ] = None,
    output: Annotated[
        Path,
        cyclopts.Parameter(name=["--output", "-o"], help="Output directory for PDFs"),
    ] = Path("."),
    scihub: Annotated[
        bool,
        cyclopts.Parameter(name="--scihub", help="Enable Sci-Hub fallback (use at your own risk)"),
    ] = False,
    host_concurrency: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--host-concurrency",
            help="Concurrency: '3' (all hosts) or 'arxiv.org=2,api.unpaywall.org=3' (per-host)",
        ),
    ] = None,
) -> None:
    """Download papers by DOI."""
    dois: list[str] = []

    # Determine input source
    if from_file is not None:
        # Read DOIs from file
        if not from_file.exists():
            print(f"Error: File not found: {from_file}", file=sys.stderr)
            sys.exit(1)
        dois = _parse_dois_from_file(from_file)
    elif doi is not None:
        # Use positional DOI argument
        dois = [doi]
    elif not sys.stdin.isatty():
        # Read from stdin (piped JSON)
        dois = _parse_dois_from_stdin()

    if not dois:
        print(
            "Error: No DOIs provided. Use positional arg, --from file, or pipe JSON.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Print header
    print(f"Downloading {len(dois)} papers to {output}/")

    # Run downloads
    success_count, fail_count = asyncio.run(_run_downloads(dois, output, scihub, host_concurrency))

    # Print summary
    total = success_count + fail_count
    print(f"Downloaded: {success_count}/{total} | Failed: {fail_count}")


async def _get_paper(
    paper_id: str, providers: list[str]
) -> tuple[list[Paper], dict[str, Exception]]:
    """Get a paper from multiple providers and return (papers, errors)."""
    papers: list[Paper] = []
    errors: dict[str, Exception] = {}

    for pname in providers:
        if pname not in GET_PROVIDERS:
            errors[pname] = Exception(f"Provider {pname} does not support get()")
            continue

        provider = GET_PROVIDERS[pname]()
        try:
            async with provider:
                paper = await provider.get(paper_id)
                if paper:
                    papers.append(paper)
        except Exception as e:
            errors[pname] = e

    return papers, errors


@app.command(name="get")
def get(
    paper_id: Annotated[str, cyclopts.Parameter(help="DOI or provider-specific paper ID")],
    providers: Annotated[
        list[str],
        cyclopts.Parameter(
            name=["--provider", "-p"],
            help="Providers to query (openalex, semantic_scholar, crossref, arxiv, scopus)",
        ),
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
    merge: Annotated[
        bool,
        cyclopts.Parameter(name="--merge", help="Merge results from multiple providers"),
    ] = True,
) -> None:
    """Fetch a specific paper by DOI or ID."""
    # Normalize providers (support comma-separated values)
    providers = [p.strip() for item in providers for p in item.split(",")]

    # Validate providers
    invalid = [p for p in providers if p not in GET_PROVIDERS]
    if invalid:
        print(f"Error: Unknown or unsupported providers: {invalid}", file=sys.stderr)
        print(f"Available: {list(GET_PROVIDERS.keys())}", file=sys.stderr)
        sys.exit(1)

    # Validate format early
    try:
        exporter = get_exporter(format)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Fetch paper from providers
    papers, errors = asyncio.run(_get_paper(paper_id, providers))

    if not papers:
        print(f"Error: Paper not found: {paper_id}", file=sys.stderr)
        for pname, error in errors.items():
            print(f"  {pname}: {error}", file=sys.stderr)
        sys.exit(1)

    # Merge results if requested and multiple papers found
    if merge and len(papers) > 1:
        papers = [merge_papers(papers)]

    result = SearchResult(papers=papers)

    # Export results
    if output:
        exporter.export(result, output)
        print(f"Exported to {output}")
    elif format == "tree":
        tree_exporter = TreeExporter()
        for paper in papers:
            print(tree_exporter.format_paper(paper))
    else:
        print(exporter.to_string(result))

    # Report errors (local to this command, not in SearchResult)
    if errors:
        for pname, error in errors.items():
            print(f"[WARN] {pname}: {error}", file=sys.stderr)


@app.command(name="index")
def index_cmd(
    directory: Annotated[
        Path,
        cyclopts.Parameter(help="Directory containing PDF files to index"),
    ],
    recursive: Annotated[
        bool,
        cyclopts.Parameter(name=["--recursive", "-r"], help="Recursively index subdirectories"),
    ] = False,
) -> None:
    """Index PDF files for fulltext search."""
    from scimesh.fulltext import FulltextIndex, extract_text_from_pdf

    if not directory.exists():
        print(f"Error: Directory not found: {directory}", file=sys.stderr)
        sys.exit(1)

    if not directory.is_dir():
        print(f"Error: Not a directory: {directory}", file=sys.stderr)
        sys.exit(1)

    index = FulltextIndex()

    # Find PDF files
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdf_files = list(directory.glob(pattern))

    if not pdf_files:
        print(f"No PDF files found in {directory}")
        return

    print(f"Indexing {len(pdf_files)} PDF files...")

    indexed = 0
    failed = 0

    for pdf_path in pdf_files:
        # Use filename (without .pdf) as paper ID
        paper_id = pdf_path.stem

        # Extract text
        text = extract_text_from_pdf(pdf_path)
        if text:
            index.add(paper_id, text)
            print(f"  [OK] {paper_id}")
            indexed += 1
        else:
            print(f"  [FAIL] {paper_id} - could not extract text")
            failed += 1

    print(f"\nIndexed: {indexed} | Failed: {failed} | Total in index: {index.count()}")


async def _get_citations(
    paper_id: str, providers: list[str], direction: str, max_results: int
) -> tuple[list[Paper], dict[str, Exception]]:
    """Get citations from multiple providers and return (papers, errors)."""
    papers: list[Paper] = []
    errors: dict[str, Exception] = {}

    for pname in providers:
        if pname not in CITATIONS_PROVIDERS:
            errors[pname] = Exception(f"Provider {pname} does not support citations()")
            continue

        provider = CITATIONS_PROVIDERS[pname]()
        try:
            async with provider:
                count = 0
                stream = provider.citations(paper_id, direction=direction, max_results=max_results)
                async for paper in stream:  # type: ignore
                    papers.append(paper)
                    count += 1
                    if count >= max_results:
                        break
        except NotImplementedError:
            errors[pname] = Exception(f"Provider {pname} does not support citations()")
        except Exception as e:
            errors[pname] = e

    return papers, errors


@app.command(name="citations")
def citations(
    paper_id: Annotated[str, cyclopts.Parameter(help="DOI or provider-specific paper ID")],
    direction: Annotated[
        str,
        cyclopts.Parameter(
            name=["--direction", "-d"],
            help="Citation direction: in (citing this paper), out (cited by this paper), both",
        ),
    ] = "both",
    providers: Annotated[
        list[str],
        cyclopts.Parameter(
            name=["--provider", "-p"],
            help="Providers to query (openalex, semantic_scholar, scopus)",
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
        cyclopts.Parameter(name=["--max", "-n"], help="Maximum number of results"),
    ] = 100,
    no_dedupe: Annotated[
        bool,
        cyclopts.Parameter(name="--no-dedupe", help="Disable deduplication"),
    ] = False,
) -> None:
    """Get papers citing or cited by a specific paper."""
    # Validate direction
    if direction not in ("in", "out", "both"):
        print(f"Error: Invalid direction: {direction}", file=sys.stderr)
        print("Valid options: in, out, both", file=sys.stderr)
        sys.exit(1)

    # Normalize providers (support comma-separated values)
    providers = [p.strip() for item in providers for p in item.split(",")]

    # Validate providers
    invalid = [p for p in providers if p not in CITATIONS_PROVIDERS]
    if invalid:
        print(f"Error: Unknown or unsupported providers: {invalid}", file=sys.stderr)
        print(f"Available: {list(CITATIONS_PROVIDERS.keys())}", file=sys.stderr)
        sys.exit(1)

    # Validate format early
    try:
        exporter = get_exporter(format)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Fetch citations from providers
    papers, errors = asyncio.run(_get_citations(paper_id, providers, direction, max_results))

    if not papers and not errors:
        print(f"No citations found for: {paper_id}", file=sys.stderr)
        sys.exit(0)

    result = SearchResult(papers=papers)

    # Dedupe if requested
    if not no_dedupe:
        result = result.dedupe()

    # Export results
    if output:
        exporter.export(result, output)
        print(f"Exported {len(result.papers)} papers to {output}")
    elif format == "tree":
        tree_exporter = TreeExporter()
        for i, paper in enumerate(result.papers):
            if i > 0:
                print()
            print(tree_exporter.format_paper(paper))
        print(f"\nTotal: {len(result.papers)} papers", file=sys.stderr)
    else:
        print(exporter.to_string(result))

    # Report errors
    if errors:
        for pname, error in errors.items():
            print(f"[WARN] {pname}: {error}", file=sys.stderr)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
