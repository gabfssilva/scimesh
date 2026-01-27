# scimesh/export/ris.py
from scimesh.models import SearchResult

from .base import Exporter


class RisExporter(Exporter):
    """Export results to RIS format."""

    def to_string(self, result: SearchResult) -> str:
        entries: list[str] = []
        for paper in result.papers:
            lines = [
                "TY  - JOUR",
                f"TI  - {paper.title}",
            ]

            for author in paper.authors:
                lines.append(f"AU  - {author.name}")

            lines.append(f"PY  - {paper.year}")

            if paper.doi:
                lines.append(f"DO  - {paper.doi}")
            if paper.journal:
                lines.append(f"JO  - {paper.journal}")
            if paper.abstract:
                lines.append(f"AB  - {paper.abstract}")
            if paper.url:
                lines.append(f"UR  - {paper.url}")

            for topic in paper.topics:
                lines.append(f"KW  - {topic}")

            lines.append("ER  - ")
            entries.append("\n".join(lines))

        return "\n\n".join(entries)
