# scimesh/cli.py
import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated

import cyclopts

from scimesh import search as do_search
from scimesh import take
from scimesh.download import download_papers
from scimesh.export import get_exporter
from scimesh.export.tree import TreeExporter
from scimesh.providers import Arxiv, OpenAlex, Scopus

app = cyclopts.App(
    name="scimesh",
    help="Scientific paper search across multiple providers.",
)

PROVIDERS = {
    "arxiv": Arxiv,
    "openalex": OpenAlex,
    "scopus": Scopus,
}


async def _stream_search(
    query: str,
    provider_instances: list,
    max_results: int,
    on_error: str,
    tree_exporter: TreeExporter,
    total: int | None = None,
) -> int:
    """Stream search results, printing each paper as it arrives."""
    count = 0
    seen: set[str] = set()  # For deduplication

    stream = do_search(
        query,
        providers=provider_instances,
        max_results=max_results,
        on_error=on_error,  # type: ignore
        stream=True,
    )
    if total is not None:
        stream = take(total, stream)

    async for paper in stream:
        # Dedupe by DOI or title+year
        key = paper.doi if paper.doi else f"{paper.title.lower()}:{paper.year}"
        if key in seen:
            continue
        seen.add(key)

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
            name=["--provider", "-p"], help="Providers to search (arxiv, openalex, scopus)"
        ),
    ] = ["arxiv", "openalex"],
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
        cyclopts.Parameter(name=["--max", "-n"], help="Maximum results per provider"),
    ] = 100,
    total: Annotated[
        int | None,
        cyclopts.Parameter(
            name=["--total", "-t"], help="Maximum total results across all providers"
        ),
    ] = None,
    on_error: Annotated[
        str,
        cyclopts.Parameter(name="--on-error", help="Error handling: fail, warn, ignore"),
    ] = "warn",
    no_dedupe: Annotated[
        bool,
        cyclopts.Parameter(name="--no-dedupe", help="Disable deduplication"),
    ] = False,
) -> None:
    """Search for scientific papers across multiple providers."""
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

    # Create provider instances
    provider_instances = [PROVIDERS[p]() for p in providers]

    # Use streaming for tree format without output file (only in terminal)
    if format == "tree" and output is None:
        count = asyncio.run(
            _stream_search(
                query,
                provider_instances,
                max_results,
                on_error,
                TreeExporter(),
                total,
            )
        )
        print(f"\nTotal: {count} papers", file=sys.stderr)
        return

    # Non-streaming path for other formats or file output
    result = asyncio.run(
        do_search(
            query,
            providers=provider_instances,
            max_results=max_results,
            on_error=on_error,  # type: ignore
            dedupe=not no_dedupe,
        )
    )

    # Apply total limit
    if total is not None and len(result.papers) > total:
        result.papers = result.papers[:total]

    # Export results
    if output:
        exporter.export(result, output)
        print(f"Exported {len(result.papers)} papers to {output}")
    else:
        print(exporter.to_string(result))

    # Report errors
    if result.errors:
        for provider_name, error in result.errors.items():
            print(f"[WARN] {provider_name}: {error}", file=sys.stderr)

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


def _parse_dois_from_stdin() -> list[str]:
    """Parse DOIs from JSON piped via stdin.

    Expects JSON with structure: {"papers": [{"doi": "...", "url": "..."}, ...]}
    Falls back to constructing arXiv DOIs from URLs when DOI is missing.
    """
    try:
        data = json.load(sys.stdin)
        papers = data.get("papers", [])
        dois = []
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
    dois = []
    with filepath.open() as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                dois.append(line)
    return dois


async def _run_downloads(
    dois: list[str], output_dir: Path, use_scihub: bool = False
) -> tuple[int, int]:
    """Run downloads and print progress. Returns (success_count, fail_count)."""
    from scimesh.download import Downloader, OpenAccessDownloader, SciHubDownloader

    downloaders: list[Downloader] = [OpenAccessDownloader()]
    if use_scihub:
        downloaders.append(SciHubDownloader())

    success_count = 0
    fail_count = 0

    async for result in download_papers(dois, output_dir, downloaders=downloaders):
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
    success_count, fail_count = asyncio.run(_run_downloads(dois, output, scihub))

    # Print summary
    total = success_count + fail_count
    print(f"Downloaded: {success_count}/{total} | Failed: {fail_count}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
