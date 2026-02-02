"""YAML repository for workspace persistence."""

from pathlib import Path

import yaml

from scimesh.workspace.models import (
    CollectionWorkspace,
    ExplorationWorkspace,
    LogEntry,
    PaperEntry,
    PaperIndex,
    SLRWorkspace,
    parse_workspace,
)


class WorkspaceNotFoundError(Exception):
    """Workspace not found."""


class WorkspaceExistsError(Exception):
    """Workspace already exists."""


class YamlWorkspaceRepository:
    """Repository for persisting workspace data to YAML files."""

    def __init__(self, root: Path):
        self.root = root

    @property
    def _index_path(self) -> Path:
        return self.root / "index.yaml"

    @property
    def _log_path(self) -> Path:
        return self.root / "log.yaml"

    @property
    def _papers_path(self) -> Path:
        return self.root / "papers.yaml"

    def load(self) -> SLRWorkspace | ExplorationWorkspace | CollectionWorkspace:
        if not self._index_path.exists():
            raise WorkspaceNotFoundError(f"Workspace not found at {self.root}")
        yaml_content = self._index_path.read_text()
        data = yaml.safe_load(yaml_content)
        return parse_workspace(data)

    def save(self, workspace: SLRWorkspace | ExplorationWorkspace | CollectionWorkspace) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        data = workspace.model_dump(mode="json", exclude_none=True)
        yaml_content = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
        self._index_path.write_text(yaml_content)

    def exists(self) -> bool:
        return self._index_path.exists()

    def load_log(self) -> list[LogEntry]:
        if not self._log_path.exists():
            return []
        yaml_content = self._log_path.read_text()
        raw_list = yaml.safe_load(yaml_content) or []
        return [LogEntry.model_validate(entry) for entry in raw_list]

    def save_log(self, entries: list[LogEntry]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        data = [entry.model_dump(mode="json", exclude_none=True) for entry in entries]
        yaml_content = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
        self._log_path.write_text(yaml_content)

    def append_log(self, entry: LogEntry) -> None:
        entries = self.load_log()
        entries.append(entry)
        self.save_log(entries)

    def load_papers(self) -> list[PaperEntry]:
        if not self._papers_path.exists():
            return []
        yaml_content = self._papers_path.read_text()
        raw_list = yaml.safe_load(yaml_content) or []
        return [PaperEntry.model_validate(entry) for entry in raw_list]

    def save_papers(self, papers: list[PaperEntry]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        data = [paper.model_dump(mode="json", exclude_none=True) for paper in papers]
        yaml_content = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
        self._papers_path.write_text(yaml_content)

    def _paper_index_path(self, path: str) -> Path:
        return self.root / path / "index.yaml"

    def load_paper(self, path: str) -> PaperIndex:
        paper_path = self._paper_index_path(path)
        if not paper_path.exists():
            raise FileNotFoundError(f"Paper not found at {paper_path}")
        yaml_content = paper_path.read_text()
        data = yaml.safe_load(yaml_content)
        return PaperIndex.model_validate(data)

    def save_paper(self, path: str, paper: PaperIndex) -> None:
        paper_path = self._paper_index_path(path)
        paper_path.parent.mkdir(parents=True, exist_ok=True)
        data = paper.model_dump(mode="json", exclude_none=True)
        yaml_content = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
        paper_path.write_text(yaml_content)

    def paper_exists(self, path: str) -> bool:
        return self._paper_index_path(path).exists()
