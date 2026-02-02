from .base import Exporter
from .bibtex import BibtexExporter
from .csv import CsvExporter
from .json import JsonExporter
from .paper_exporter import VaultExporter
from .ris import RisExporter
from .tree import TreeExporter

EXPORTERS: dict[str, type[Exporter]] = {
    "csv": CsvExporter,
    "json": JsonExporter,
    "bibtex": BibtexExporter,
    "bib": BibtexExporter,
    "ris": RisExporter,
    "tree": TreeExporter,
}

ALL_FORMATS = list(EXPORTERS.keys()) + ["workspace"]


def get_exporter(format: str) -> Exporter:
    """Get an exporter instance by format name.

    Note: VaultExporter is not included here as it has a different interface.
    Use VaultExporter directly for workspace format.
    """
    format_lower = format.lower()
    if format_lower not in EXPORTERS:
        raise ValueError(f"Unknown export format: {format}. Available: {ALL_FORMATS}")
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
    "ALL_FORMATS",
]
