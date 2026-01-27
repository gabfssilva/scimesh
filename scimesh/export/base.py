# scimesh/export/base.py
from abc import ABC, abstractmethod
from pathlib import Path

from scimesh.models import SearchResult


class Exporter(ABC):
    """Base class for result exporters."""

    @abstractmethod
    def to_string(self, result: SearchResult) -> str:
        """Export results to string."""
        ...

    def export(self, result: SearchResult, path: Path) -> None:
        """Export results to file."""
        path.write_text(self.to_string(result), encoding="utf-8")
