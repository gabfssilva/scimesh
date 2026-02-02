"""YAML repository for workspace persistence."""

from datetime import UTC, datetime
from pathlib import Path

import yaml

from scimesh.workspace.models import (
    CollectionWorkspace,
    ExplorationWorkspace,
    LogEntry,
    PaperEntry,
    PaperIndex,
    SLRWorkspace,
    Stats,
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

    def set_paper_screening(self, paper_path: str, status: str, reason: str) -> None:
        """Set screening status for a paper.

        Args:
            paper_path: Relative path to paper (e.g., papers/2024/smith)
            status: included, excluded, or maybe
            reason: Reason for the decision
        """
        paper = self.load_paper(paper_path)
        now = datetime.now(UTC)

        paper_dict = paper.model_dump(mode="json", exclude_none=True)
        paper_dict["screening"] = {
            "status": status,
            "reason": reason,
            "screened_at": now.isoformat().replace("+00:00", "Z"),
        }

        paper_yaml_path = self.root / paper_path / "index.yaml"
        yaml_content = yaml.safe_dump(paper_dict, default_flow_style=False, allow_unicode=True)
        paper_yaml_path.write_text(yaml_content)

        papers = self.load_papers()
        updated = [
            PaperEntry(
                path=p.path,
                doi=p.doi,
                title=p.title,
                status=status if p.path == paper_path else p.status,
                search_ids=p.search_ids,
            )
            for p in papers
        ]
        self.save_papers(updated)

    def update_stats(self) -> Stats:
        """Recalculate and update workspace statistics."""
        workspace = self.load()
        papers = self.load_papers()

        total = 0
        with_pdf = 0
        included = 0
        excluded = 0
        maybe = 0
        unscreened = 0

        for entry in papers:
            paper_path = self.root / entry.path
            if not paper_path.exists():
                continue

            total += 1

            if (paper_path / "fulltext.pdf").exists():
                with_pdf += 1

            status = entry.status
            if status == "included":
                included += 1
            elif status == "excluded":
                excluded += 1
            elif status == "maybe":
                maybe += 1
            else:
                unscreened += 1

        new_stats = Stats(
            total=total,
            with_pdf=with_pdf,
            included=included,
            excluded=excluded,
            maybe=maybe,
            unscreened=unscreened,
        )

        workspace.stats = new_stats
        self.save(workspace)

        return new_stats
