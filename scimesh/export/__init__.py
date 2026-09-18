from .base import Exporter
from .bibtex import BibtexExporter
from .csv import CsvExporter
from .json import JsonExporter
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

ALL_FORMATS = list(EXPORTERS)


def get_exporter(format: str) -> Exporter:
    """Get an exporter instance by format name."""
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
    "get_exporter",
    "ALL_FORMATS",
]
