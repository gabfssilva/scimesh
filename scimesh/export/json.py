# scimesh/export/json.py
import json
from dataclasses import asdict
from datetime import date
from typing import Any

from scimesh.models import SearchResult

from .base import Exporter


class JsonExporter(Exporter):
    """Export results to JSON format."""

    def __init__(self, indent: int = 2):
        self.indent = indent

    def to_string(self, result: SearchResult) -> str:
        def default_serializer(obj: Any) -> str:
            if isinstance(obj, date):
                return obj.isoformat()
            if isinstance(obj, Exception):
                return str(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        data = {
            "papers": [asdict(p) for p in result.papers],
            "total": len(result.papers),
            "by_provider": result.total_by_provider,
        }
        return json.dumps(data, indent=self.indent, ensure_ascii=False, default=default_serializer)
