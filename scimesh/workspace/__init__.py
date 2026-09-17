"""Workspace module for managing paper collections and SLR workflows."""

from scimesh.workspace.models import (
    CollectionWorkspace,
    Constraints,
    ExplorationWorkspace,
    Framework,
    LogEntry,
    PaperEntry,
    PaperIndex,
    Screening,
    SearchResults,
    SLRWorkspace,
    Stats,
    Workspace,
    parse_workspace,
)
from scimesh.workspace.operations import (
    build_prisma_report,
    ingest_papers,
    load_or_exit,
    load_strict_or_exit,
)
from scimesh.workspace.repository import (
    WorkspaceExistsError,
    WorkspaceNotFoundError,
    YamlWorkspaceRepository,
)

__all__ = [
    "CollectionWorkspace",
    "Constraints",
    "ExplorationWorkspace",
    "Framework",
    "LogEntry",
    "PaperEntry",
    "PaperIndex",
    "Screening",
    "SearchResults",
    "SLRWorkspace",
    "Stats",
    "Workspace",
    "WorkspaceExistsError",
    "WorkspaceNotFoundError",
    "YamlWorkspaceRepository",
    "build_prisma_report",
    "ingest_papers",
    "load_or_exit",
    "load_strict_or_exit",
    "parse_workspace",
]
