# scimesh/export/bibtex.py
import re

from scimesh.models import Paper, SearchResult

from .base import Exporter


class BibtexExporter(Exporter):
    """Export results to BibTeX format."""

    def to_string(self, result: SearchResult) -> str:
        entries: list[str] = []
        for i, paper in enumerate(result.papers):
            entry = self._paper_to_bibtex(paper, i)
            entries.append(entry)
        return "\n\n".join(entries)

    def _paper_to_bibtex(self, paper: Paper, index: int) -> str:
        # Generate citation key: first_author_year_index
        if paper.authors:
            first_author = paper.authors[0].name.split()[-1].lower()
            first_author = re.sub(r"[^a-z]", "", first_author)
        else:
            first_author = "unknown"
        key = f"{first_author}{paper.year}_{index}"

        # Author string
        authors = " and ".join(a.name for a in paper.authors)

        lines = [
            f"@article{{{key},",
            f"  title = {{{paper.title}}},",
            f"  author = {{{authors}}},",
            f"  year = {{{paper.year}}},",
        ]

        if paper.doi:
            lines.append(f"  doi = {{{paper.doi}}},")
        if paper.journal:
            lines.append(f"  journal = {{{paper.journal}}},")
        if paper.abstract:
            abstract = paper.abstract.replace("{", "\\{").replace("}", "\\}")
            lines.append(f"  abstract = {{{abstract}}},")
        if paper.url:
            lines.append(f"  url = {{{paper.url}}},")

        lines.append("}")
        return "\n".join(lines)
