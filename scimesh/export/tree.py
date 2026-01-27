# scimesh/export/tree.py
"""Tree view exporter for search results."""

from scimesh.export.base import Exporter
from scimesh.models import Paper, SearchResult


class TreeExporter(Exporter):
    """Export results as a tree view with paper as root."""

    def _get_url(self, paper: Paper) -> str:
        """Get the best available URL for a paper."""
        if paper.url:
            return paper.url
        if paper.doi:
            return f"https://doi.org/{paper.doi}"
        return ""

    def _format_authors(self, paper: Paper, max_authors: int = 3) -> str:
        """Format authors, truncating if too many."""
        if not paper.authors:
            return "Unknown"
        names = [a.name for a in paper.authors]
        if len(names) <= max_authors:
            return ", ".join(names)
        return ", ".join(names[:max_authors]) + f" +{len(names) - max_authors}"

    def _truncate(self, text: str, max_len: int = 80) -> str:
        """Truncate text to max length."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def format_paper(self, paper: Paper) -> str:
        """Format a single paper as tree view."""
        lines: list[str] = []

        # Title as root
        lines.append(self._truncate(paper.title))

        # Metadata as children
        lines.append(f"├── Year: {paper.year}")
        lines.append(f"├── Authors: {self._format_authors(paper)}")

        url = self._get_url(paper)
        if url:
            lines.append(f"└── URL: {url}")
        else:
            # Remove last ├ and replace with └ for authors if no URL
            lines[-1] = lines[-1].replace("├──", "└──")

        return "\n".join(lines)

    def to_string(self, result: SearchResult) -> str:
        """Export results as tree view."""
        if not result.papers:
            return "No papers found."

        formatted = [self.format_paper(paper) for paper in result.papers]
        return "\n\n".join(formatted)
