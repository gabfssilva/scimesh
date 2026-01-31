# scimesh/export/vault.py
"""Vault exporter for Obsidian-compatible folder structure."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from scimesh.models import Paper, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class VaultStats:
    """Statistics for vault export."""

    total: int = 0
    by_provider: dict[str, int] = field(default_factory=dict)
    with_pdf: int = 0
    deduplicated: int = 0
    skipped: int = 0


def generate_paper_slug(paper: Paper, max_slug_words: int = 6) -> str:
    """Generate paper slug in format: author-title-words.

    Args:
        paper: The paper to generate a slug for.
        max_slug_words: Maximum words in the title slug.

    Returns:
        A filesystem-safe slug like "vaswani-attention-is-all-you".
    """
    # Extract first author's surname
    if paper.authors:
        first_author = paper.authors[0].name
        # Take last word as surname (handles "First Last" and "Last, First")
        surname = first_author.split()[-1] if " " in first_author else first_author
        surname = _slugify(surname)
    else:
        surname = "unknown"

    # Create title slug
    title_slug = _slugify(paper.title)
    words = title_slug.split("-")
    truncated_slug = "-".join(words[:max_slug_words])

    return f"{surname}-{truncated_slug}"


def get_paper_path(paper: Paper, base_dir: Path, max_slug_words: int = 6) -> tuple[Path, str]:
    """Get the full path for a paper in the vault structure.

    Papers are organized as: papers/{year}/{slug}/

    Args:
        paper: The paper to get path for.
        base_dir: Base vault directory.
        max_slug_words: Maximum words in the title slug.

    Returns:
        Tuple of (full_path, relative_path_string).
        relative_path_string is used for papers.yaml tracking.
    """
    year = str(paper.year)
    slug = generate_paper_slug(paper, max_slug_words)
    relative_path = f"papers/{year}/{slug}"
    full_path = base_dir / "papers" / year / slug
    return full_path, relative_path


def _slugify(text: str) -> str:
    """Convert text to lowercase slug with hyphens.

    Removes accents, special characters, and normalizes whitespace.
    """
    # Remove apostrophes first (they shouldn't become hyphens)
    text = text.replace("'", "")

    # Normalize unicode (remove accents)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Lowercase
    text = text.lower()

    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)

    # Remove leading/trailing hyphens
    text = text.strip("-")

    # Collapse multiple hyphens
    text = re.sub(r"-+", "-", text)

    return text


def build_paper_index(
    paper: Paper,
    pdf_filename: str | None,
    additional_sources: list[str] | None = None,
) -> str:
    """Build YAML content for paper index.yaml.

    Args:
        paper: The paper to serialize.
        pdf_filename: Name of PDF file if downloaded, None otherwise.
        additional_sources: Additional sources beyond paper.source (from dedup).

    Returns:
        YAML string for the paper's index.yaml.
    """
    # Build sources list
    sources = [paper.source]
    if additional_sources:
        sources.extend(additional_sources)
    sources = sorted(set(sources))

    # Build URLs dict
    urls: dict[str, str] = {}
    if paper.url:
        urls[paper.source] = paper.url
    # Check extras for additional URLs
    for key, value in paper.extras.items():
        if key.endswith("_url") and isinstance(value, str):
            source_name = key.replace("_url", "")
            urls[source_name] = value

    # Build data dict (only include non-None fields)
    data: dict[str, object] = {
        "title": paper.title,
        "authors": [a.name for a in paper.authors],
        "year": paper.year,
    }

    if paper.doi:
        data["doi"] = paper.doi

    data["sources"] = sources

    if urls:
        data["urls"] = urls

    if paper.topics:
        data["tags"] = sorted(paper.topics)

    if paper.citations_count is not None:
        data["citations"] = paper.citations_count

    if paper.journal:
        data["journal"] = paper.journal

    if paper.open_access:
        data["open_access"] = paper.open_access

    if pdf_filename:
        data["pdf"] = pdf_filename

    if paper.abstract:
        data["abstract"] = paper.abstract

    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def build_root_index(
    query: str,
    providers: list[str],
    stats: VaultStats,
    papers: list[dict[str, str]],
    existing_data: dict | None = None,
) -> str:
    """Build YAML content for root index.yaml.

    If existing_data is provided, merges with existing data:
    - Preserves original searched_at
    - Adds updated_at timestamp
    - Merges stats (sums totals)
    - Merges papers list (deduplicates by path)

    Args:
        query: The search query used.
        providers: List of providers searched.
        stats: Export statistics.
        papers: List of paper entries with path, doi, title.
        existing_data: Existing index.yaml data if updating.

    Returns:
        YAML string for the root index.yaml.
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    if existing_data is None:
        # New vault
        data = {
            "query": query,
            "providers": providers,
            "searched_at": now,
            "stats": {
                "total": stats.total,
                "by_provider": stats.by_provider,
                "with_pdf": stats.with_pdf,
                "deduplicated": stats.deduplicated,
                "skipped": stats.skipped,
            },
            "papers": papers,
        }
    else:
        # Update existing vault
        existing_stats = existing_data.get("stats", {})
        existing_papers = existing_data.get("papers", [])
        existing_paths = {p["path"] for p in existing_papers}

        # Merge stats
        merged_by_provider = dict(existing_stats.get("by_provider", {}))
        for prov, count in stats.by_provider.items():
            merged_by_provider[prov] = merged_by_provider.get(prov, 0) + count

        merged_stats = {
            "total": existing_stats.get("total", 0) + stats.total,
            "by_provider": merged_by_provider,
            "with_pdf": existing_stats.get("with_pdf", 0) + stats.with_pdf,
            "deduplicated": existing_stats.get("deduplicated", 0) + stats.deduplicated,
            "skipped": existing_stats.get("skipped", 0) + stats.skipped,
        }

        # Merge papers (avoid duplicates by path)
        merged_papers = list(existing_papers)
        for paper in papers:
            if paper["path"] not in existing_paths:
                merged_papers.append(paper)

        # Merge providers
        merged_providers = list(existing_data.get("providers", []))
        for prov in providers:
            if prov not in merged_providers:
                merged_providers.append(prov)

        data = {
            "query": existing_data.get("query", query),
            "providers": merged_providers,
            "searched_at": existing_data.get("searched_at", now),
            "updated_at": now,
            "stats": merged_stats,
            "papers": merged_papers,
        }

    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


class VaultExporter:
    """Export search results as Obsidian-compatible vault structure."""

    def __init__(
        self,
        downloader: Any | None = None,
        use_scihub: bool = False,
        max_concurrent_downloads: int = 5,
    ):
        """Initialize VaultExporter.

        Args:
            downloader: Optional FallbackDownloader for PDF downloads.
            use_scihub: Whether Sci-Hub fallback is enabled.
            max_concurrent_downloads: Maximum concurrent PDF downloads.
        """
        self.downloader = downloader
        self.use_scihub = use_scihub
        self.max_concurrent_downloads = max_concurrent_downloads

    def export(
        self,
        result: SearchResult,
        output_dir: Path,
    ) -> VaultStats:
        """Export papers to vault structure.

        Args:
            result: Search results to export.
            output_dir: Directory to create vault in.

        Returns:
            VaultStats with export statistics.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        stats = VaultStats()

        # Get existing paper paths from papers.yaml to check for skips
        existing_paths: set[str] = set()
        papers_yaml_path = output_dir / "papers.yaml"
        if papers_yaml_path.exists():
            papers_data = yaml.safe_load(papers_yaml_path.read_text())
            if papers_data:
                existing_paths = {p["path"] for p in papers_data}

        for paper in result.papers:
            paper_dir, relative_path = get_paper_path(paper, output_dir)

            # Skip if already exists
            if paper_dir.exists() or relative_path in existing_paths:
                stats.skipped += 1
                logger.debug("Skipping existing: %s", relative_path)
                continue

            # Create paper folder
            paper_dir.mkdir(parents=True, exist_ok=True)

            # Download PDF if possible (placeholder - async handled in CLI)
            pdf_filename: str | None = None

            # Write paper index.yaml
            paper_index = build_paper_index(paper, pdf_filename)
            (paper_dir / "index.yaml").write_text(paper_index, encoding="utf-8")

            stats.total += 1
            stats.by_provider[paper.source] = stats.by_provider.get(paper.source, 0) + 1

            logger.debug("Exported: %s", relative_path)

        return stats

    async def export_async(
        self,
        result: SearchResult,
        output_dir: Path,
    ) -> VaultStats:
        """Export papers to vault structure with async PDF downloads.

        Args:
            result: Search results to export.
            output_dir: Directory to create vault in.

        Returns:
            VaultStats with export statistics.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        stats = VaultStats()

        # Get existing paper paths from papers.yaml to check for skips
        existing_paths: set[str] = set()
        papers_yaml_path = output_dir / "papers.yaml"
        if papers_yaml_path.exists():
            papers_data = yaml.safe_load(papers_yaml_path.read_text())
            if papers_data:
                existing_paths = {p["path"] for p in papers_data}

        # Filter papers to export (skip existing)
        papers_to_export: list[tuple[Paper, str, Path]] = []
        for paper in result.papers:
            paper_dir, relative_path = get_paper_path(paper, output_dir)

            if paper_dir.exists() or relative_path in existing_paths:
                stats.skipped += 1
                logger.debug("Skipping existing: %s", relative_path)
                continue

            papers_to_export.append((paper, relative_path, paper_dir))

        # Download PDFs concurrently
        semaphore = asyncio.Semaphore(self.max_concurrent_downloads)

        async def download_pdf(paper: Paper, relative_path: str) -> bytes | None:
            """Download PDF with concurrency limit."""
            if not self.downloader:
                return None
            if not paper.doi:
                logger.info("  [--] No DOI: %s", relative_path)
                return None

            async with semaphore:
                try:
                    pdf_bytes = await self.downloader.download(paper.doi)
                    if pdf_bytes:
                        logger.info("  [OK] PDF: %s", relative_path)
                        return pdf_bytes
                    logger.info("  [--] PDF not found: %s", relative_path)
                except Exception as e:
                    logger.info("  [!!] PDF error: %s - %s", relative_path, e)
                return None

        # Start all downloads concurrently
        download_tasks = [
            download_pdf(paper, relative_path) for paper, relative_path, _ in papers_to_export
        ]
        pdf_results = await asyncio.gather(*download_tasks)

        # Write papers to disk (sequential to avoid I/O contention)
        for (paper, relative_path, paper_dir), pdf_bytes in zip(
            papers_to_export, pdf_results, strict=True
        ):
            paper_dir.mkdir(parents=True, exist_ok=True)

            pdf_filename: str | None = None
            if pdf_bytes:
                pdf_path = paper_dir / "fulltext.pdf"
                pdf_path.write_bytes(pdf_bytes)
                pdf_filename = "fulltext.pdf"
                stats.with_pdf += 1

            # Write paper index.yaml
            paper_index = build_paper_index(paper, pdf_filename)
            (paper_dir / "index.yaml").write_text(paper_index, encoding="utf-8")

            stats.total += 1
            stats.by_provider[paper.source] = stats.by_provider.get(paper.source, 0) + 1
            logger.debug("Exported: %s", relative_path)

        return stats
