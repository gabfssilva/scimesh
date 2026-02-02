"""Data models for workspace management using Pydantic."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Discriminator, Field, Tag, TypeAdapter


class Constraints(BaseModel):
    """Search constraints for a workspace."""

    databases: list[str] = Field(default_factory=lambda: ["openalex", "semantic_scholar"])
    year_range: str | None = None


class Stats(BaseModel):
    """Statistics for a workspace."""

    total: int = 0
    with_pdf: int = 0
    included: int = 0
    excluded: int = 0
    maybe: int = 0
    unscreened: int = 0


class Framework(BaseModel):
    """Research question framework (PICO, SPIDER, or custom)."""

    type: str
    fields: dict[str, str] = Field(default_factory=dict)


class SLRWorkspace(BaseModel):
    """Systematic Literature Review workspace."""

    type: Literal["slr"] = "slr"
    question: str
    constraints: Constraints = Field(default_factory=Constraints)
    stats: Stats = Field(default_factory=Stats)
    framework: Framework
    inclusion: list[str] = Field(default_factory=list)
    exclusion: list[str] = Field(default_factory=list)


class ExplorationWorkspace(BaseModel):
    """Exploration workspace for broad literature surveys."""

    type: Literal["exploration"] = "exploration"
    question: str
    constraints: Constraints = Field(default_factory=Constraints)
    stats: Stats = Field(default_factory=Stats)
    limit: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CollectionWorkspace(BaseModel):
    """Simple collection workspace for managing paper lists."""

    type: Literal["collection"] = "collection"
    question: str
    constraints: Constraints = Field(default_factory=Constraints)
    stats: Stats = Field(default_factory=Stats)


def _get_workspace_type(v: Any) -> str:
    """Extract workspace type for discriminated union."""
    if isinstance(v, dict):
        return v.get("type", "")
    return getattr(v, "type", "")


Workspace = Annotated[
    Annotated[SLRWorkspace, Tag("slr")]
    | Annotated[ExplorationWorkspace, Tag("exploration")]
    | Annotated[CollectionWorkspace, Tag("collection")],
    Discriminator(_get_workspace_type),
]

_workspace_adapter: TypeAdapter[Workspace] = TypeAdapter(Workspace)


def parse_workspace(
    data: dict[str, Any],
) -> SLRWorkspace | ExplorationWorkspace | CollectionWorkspace:
    """Parse a workspace dictionary into the appropriate workspace type.

    Args:
        data: Dictionary containing workspace data with a 'type' field.

    Returns:
        The appropriate workspace instance based on the type field.

    Raises:
        ValidationError: If the data is invalid or type is not recognized.
    """
    return _workspace_adapter.validate_python(data)


class SearchResults(BaseModel):
    """Results count for a search operation."""

    total: int
    unique: int


class Condensed(BaseModel):
    """Condensed paper information from exploration."""

    problem: str
    method: str
    results: str
    limitations: str | None = None
    relevance_to_exploration: str | None = None


class LogEntry(BaseModel):
    """Entry for a search/operation in the log."""

    id: str
    type: str
    query: str | None = None
    providers: list[str] = Field(default_factory=list)
    executed_at: datetime
    results: SearchResults | None = None
    seed_doi: str | None = None
    direction: str | None = None
    notes: str | None = None
    subtopics: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    saturation: bool | None = None


class PaperEntry(BaseModel):
    """Entry for a paper in the papers index."""

    path: str
    doi: str
    title: str
    status: str = "unscreened"
    search_ids: list[str] = Field(default_factory=list)


class Screening(BaseModel):
    """Screening decision for a paper."""

    status: str
    reason: str
    screened_at: datetime


class PaperIndex(BaseModel):
    """Full index/metadata for a paper."""

    title: str
    authors: list[str]
    year: int
    doi: str | None = None
    sources: list[str] = Field(default_factory=list)
    urls: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    citations: int | None = None
    journal: str | None = None
    open_access: bool | None = None
    pdf: str | None = None
    abstract: str | None = None
    screening: Screening | None = None
    subtopic: str | None = None
    relevance: str | None = None
    condensed: Condensed | None = None
