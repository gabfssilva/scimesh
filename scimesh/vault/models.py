"""Data models for vault management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ScreeningStatus(str, Enum):
    """Screening status for a paper."""

    INCLUDED = "included"
    EXCLUDED = "excluded"
    MAYBE = "maybe"
    UNSCREENED = "unscreened"


class FrameworkType(str, Enum):
    """Type of research question framework."""

    PICO = "pico"
    SPIDER = "spider"
    CUSTOM = "custom"


class FieldCategory(str, Enum):
    """Category of a framework field."""

    CONTEXT = "context"
    ACTION = "action"
    COMPARISON = "comparison"
    RESULT = "result"


@dataclass(frozen=True)
class FieldSchema:
    """Schema definition for a custom framework field."""

    name: str
    category: FieldCategory
    required: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "name": self.name,
            "category": self.category.value,
            "required": self.required,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldSchema:
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            category=FieldCategory(data.get("category", "context")),
            required=data.get("required", True),
            description=data.get("description", ""),
        )


@dataclass(frozen=True)
class Framework:
    """Research question framework (PICO, SPIDER, or custom)."""

    type: FrameworkType
    fields: dict[str, str]
    schema: tuple[FieldSchema, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, Any] = {
            "type": self.type.value,
            "fields": dict(self.fields),
        }
        if self.schema:
            result["schema"] = [fs.to_dict() for fs in self.schema]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Framework:
        """Create from dictionary."""
        schema_data = data.get("schema", [])
        schema = tuple(FieldSchema.from_dict(s) for s in schema_data)
        return cls(
            type=FrameworkType(data.get("type", "pico")),
            fields=dict(data.get("fields", {})),
            schema=schema,
        )


@dataclass(frozen=True)
class ScreeningDecision:
    """A screening decision for a paper."""

    status: ScreeningStatus
    reason: str
    screened_at: datetime


@dataclass(frozen=True)
class Protocol:
    """SLR protocol definition."""

    question: str
    framework: Framework
    inclusion: tuple[str, ...] = ()
    exclusion: tuple[str, ...] = ()
    databases: tuple[str, ...] = ("arxiv", "openalex", "semantic_scholar")
    year_range: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "question": self.question,
            "framework": self.framework.to_dict(),
            "inclusion": list(self.inclusion),
            "exclusion": list(self.exclusion),
            "databases": list(self.databases),
            "year_range": self.year_range,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Protocol:
        """Create from dictionary."""
        return cls(
            question=data.get("question", ""),
            framework=Framework.from_dict(data.get("framework", {})),
            inclusion=tuple(data.get("inclusion", [])),
            exclusion=tuple(data.get("exclusion", [])),
            databases=tuple(data.get("databases", ["arxiv", "openalex", "semantic_scholar"])),
            year_range=data.get("year_range", ""),
        )


@dataclass(frozen=True)
class VaultStats:
    """Statistics for a vault."""

    total: int = 0
    included: int = 0
    excluded: int = 0
    maybe: int = 0
    unscreened: int = 0
    with_pdf: int = 0
    last_updated: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, Any] = {
            "total": self.total,
            "included": self.included,
            "excluded": self.excluded,
            "maybe": self.maybe,
            "unscreened": self.unscreened,
            "with_pdf": self.with_pdf,
        }
        if self.last_updated:
            result["last_updated"] = self.last_updated.isoformat().replace("+00:00", "Z")
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VaultStats:
        """Create from dictionary."""
        last_updated = None
        if "last_updated" in data and data["last_updated"]:
            last_updated = datetime.fromisoformat(data["last_updated"].replace("Z", "+00:00"))
        return cls(
            total=data.get("total", 0),
            included=data.get("included", 0),
            excluded=data.get("excluded", 0),
            maybe=data.get("maybe", 0),
            unscreened=data.get("unscreened", 0),
            with_pdf=data.get("with_pdf", 0),
            last_updated=last_updated,
        )


@dataclass(frozen=True)
class SearchResults:
    """Results count for a search."""

    total: int
    unique: int

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary for YAML serialization."""
        return {"total": self.total, "unique": self.unique}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchResults:
        """Create from dictionary."""
        return cls(
            total=data.get("total", 0),
            unique=data.get("unique", 0),
        )


@dataclass(frozen=True)
class SearchEntry:
    """Entry for a search in searches.yaml."""

    id: str
    query: str
    providers: tuple[str, ...]
    executed_at: datetime
    results: SearchResults
    type: str = "search"
    seed_doi: str | None = None
    direction: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, Any] = {
            "id": self.id,
            "query": self.query,
            "providers": list(self.providers),
            "executed_at": self.executed_at.isoformat().replace("+00:00", "Z"),
            "results": self.results.to_dict(),
        }
        if self.type != "search":
            result["type"] = self.type
        if self.seed_doi:
            result["seed_doi"] = self.seed_doi
        if self.direction:
            result["direction"] = self.direction
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchEntry:
        """Create from dictionary."""
        executed_at = datetime.fromisoformat(data.get("executed_at", "").replace("Z", "+00:00"))
        return cls(
            id=data.get("id", ""),
            query=data.get("query", ""),
            providers=tuple(data.get("providers", [])),
            executed_at=executed_at,
            results=SearchResults.from_dict(data.get("results", {})),
            type=data.get("type", "search"),
            seed_doi=data.get("seed_doi"),
            direction=data.get("direction"),
        )


@dataclass(frozen=True)
class PaperEntry:
    """Entry for a paper in papers.yaml."""

    path: str
    doi: str
    title: str
    status: ScreeningStatus = ScreeningStatus.UNSCREENED
    search_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "path": self.path,
            "doi": self.doi,
            "title": self.title,
            "status": self.status.value,
            "search_ids": list(self.search_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperEntry:
        """Create from dictionary."""
        status_str = data.get("status", "unscreened")
        try:
            status = ScreeningStatus(status_str)
        except ValueError:
            status = ScreeningStatus.UNSCREENED
        return cls(
            path=data.get("path", ""),
            doi=data.get("doi", ""),
            title=data.get("title", ""),
            status=status,
            search_ids=tuple(data.get("search_ids", [])),
        )


@dataclass
class VaultIndex:
    """Root index for a vault (index.yaml)."""

    protocol: Protocol
    stats: VaultStats = field(default_factory=VaultStats)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "protocol": self.protocol.to_dict(),
            "stats": self.stats.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VaultIndex:
        """Create from dictionary."""
        return cls(
            protocol=Protocol.from_dict(data.get("protocol", {})),
            stats=VaultStats.from_dict(data.get("stats", {})),
        )


FRAMEWORK_TEMPLATES: dict[FrameworkType, tuple[FieldSchema, ...]] = {
    FrameworkType.PICO: (
        FieldSchema("population", FieldCategory.CONTEXT, True, "Who/what is being studied"),
        FieldSchema("intervention", FieldCategory.ACTION, True, "What is being applied"),
        FieldSchema("comparison", FieldCategory.COMPARISON, False, "Alternative approaches"),
        FieldSchema("outcome", FieldCategory.RESULT, True, "What is being measured"),
    ),
    FrameworkType.SPIDER: (
        FieldSchema("sample", FieldCategory.CONTEXT, True, "Group being studied"),
        FieldSchema("phenomenon", FieldCategory.ACTION, True, "Experience/behavior of interest"),
        FieldSchema("design", FieldCategory.CONTEXT, True, "Research design type"),
        FieldSchema("evaluation", FieldCategory.RESULT, True, "Outcome measures"),
        FieldSchema("research_type", FieldCategory.CONTEXT, True, "Qualitative/mixed methods"),
    ),
}
