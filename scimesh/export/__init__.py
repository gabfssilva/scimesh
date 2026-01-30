# scimesh/export/__init__.py
from .base import Exporter
from .bibtex import BibtexExporter
from .csv import CsvExporter
from .json import JsonExporter
from .ris import RisExporter
from .tree import TreeExporter
from .vault import VaultExporter

EXPORTERS: dict[str, type[Exporter] | type[VaultExporter]] = {
    "csv": CsvExporter,
    "json": JsonExporter,
    "bibtex": BibtexExporter,
    "bib": BibtexExporter,
    "ris": RisExporter,
    "tree": TreeExporter,
    "vault": VaultExporter,
}


def get_exporter(format: str) -> Exporter | VaultExporter:
    """Get an exporter instance by format name."""
    format_lower = format.lower()
    if format_lower not in EXPORTERS:
        raise ValueError(f"Unknown export format: {format}. Available: {list(EXPORTERS.keys())}")
    return EXPORTERS[format_lower]()


__all__ = [
    "Exporter",
    "CsvExporter",
    "JsonExporter",
    "BibtexExporter",
    "RisExporter",
    "TreeExporter",
    "VaultExporter",
    "get_exporter",
]
