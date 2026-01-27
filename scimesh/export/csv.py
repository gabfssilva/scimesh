# scimesh/export/csv.py
import csv
from io import StringIO

from scimesh.models import SearchResult

from .base import Exporter


class CsvExporter(Exporter):
    """Export results to CSV format."""

    def to_string(self, result: SearchResult) -> str:
        output = StringIO()
        fieldnames = [
            "title",
            "authors",
            "year",
            "doi",
            "abstract",
            "journal",
            "topics",
            "url",
            "source",
            "citations",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for paper in result.papers:
            writer.writerow(
                {
                    "title": paper.title,
                    "authors": "; ".join(a.name for a in paper.authors),
                    "year": paper.year,
                    "doi": paper.doi or "",
                    "abstract": paper.abstract or "",
                    "journal": paper.journal or "",
                    "topics": "; ".join(paper.topics),
                    "url": paper.url or "",
                    "source": paper.source,
                    "citations": paper.citations_count or "",
                }
            )

        return output.getvalue()
