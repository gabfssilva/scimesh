"""SQLite-backed cache for API responses, PDFs, extracted text and failures.

Metadata lives in ``~/.scimesh/cache.db``; PDFs are content-addressed files
under ``~/.scimesh/files/``. Everything in it is re-fetchable: deleting the
directory costs time, never work.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Self

from scimesh.models import Paper

DEFAULT_FAILURE_TTL = timedelta(days=7)
DEFAULT_RESPONSE_TTL = timedelta(days=1)

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.IGNORECASE)
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")
_ARXIV = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?$", re.IGNORECASE)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    key         TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    size        INTEGER NOT NULL,
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS texts (
    key          TEXT PRIMARY KEY,
    extractor    TEXT NOT NULL,
    content      TEXT NOT NULL,
    extracted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS responses (
    url          TEXT PRIMARY KEY,
    body         BLOB NOT NULL,
    content_type TEXT,
    fetched_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS failures (
    key       TEXT PRIMARY KEY,
    error     TEXT NOT NULL,
    failed_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS texts_fts USING fts5(
    content,
    content='texts',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS texts_ai AFTER INSERT ON texts BEGIN
    INSERT INTO texts_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS texts_ad AFTER DELETE ON texts BEGIN
    INSERT INTO texts_fts(texts_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
END;

CREATE TRIGGER IF NOT EXISTS texts_au AFTER UPDATE ON texts BEGIN
    INSERT INTO texts_fts(texts_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
    INSERT INTO texts_fts(rowid, content) VALUES (new.rowid, new.content);
END;
"""


def default_root() -> Path:
    """Cache root: ``$SCIMESH_HOME`` when set, else ``~/.scimesh``."""
    home = os.getenv("SCIMESH_HOME")
    return Path(home) if home else Path.home() / ".scimesh"


def normalize_key(identifier: str) -> str:
    """Canonical cache key for a DOI, arXiv id or provider-specific id.

    DOIs are case-insensitive, so keys are lowercased. arXiv ids collapse onto
    their DOI form; ids from other providers keep a source prefix.

    Example:
        >>> normalize_key("https://doi.org/10.1038/Nature14539")
        '10.1038/nature14539'
        >>> normalize_key("1706.03762")
        '10.48550/arxiv.1706.03762'
    """
    value = _DOI_PREFIX.sub("", identifier.strip())

    arxiv = _ARXIV.match(value)
    if arxiv:
        return f"10.48550/arxiv.{arxiv.group(1).lower()}"

    if _DOI.match(value):
        return value.lower()

    return value.lower()


def paper_key(paper: Paper) -> str | None:
    """Cache key for a paper, or None when it carries no usable identifier."""
    if paper.doi:
        return normalize_key(paper.doi)

    sources = (
        ("arxiv_id", ""),
        ("openalex_id", "openalex:"),
        ("scopus_id", "scopus:"),
        ("semanticScholarId", "s2:"),
    )
    for field, prefix in sources:
        value = paper.extras.get(field)
        if value:
            return normalize_key(f"{prefix}{value}")

    return None


def key_to_doi(key: str) -> str | None:
    """DOI for a cache key, or None when the key is a provider-specific id."""
    return key if _DOI.match(key) else None


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Counts and disk usage of the cache."""

    documents: int
    texts: int
    responses: int
    failures: int
    bytes: int


@dataclass(frozen=True, slots=True)
class GcReport:
    """Inconsistencies found and fixed by a garbage collection pass."""

    dropped_rows: int
    deleted_files: int
    expired_responses: int


class Cache:
    """API responses, PDFs, extracted text and download failures.

    Responses expire after a TTL, since metadata keeps changing. PDFs and text
    do not: a DOI resolves to the same file, and text is invalidated by the
    extractor version instead.

    Example:
        >>> cache = Cache()
        >>> path = cache.save_pdf("10.1234/paper", b"%PDF-1.4...", source="open_access")
        >>> cache.pdf("10.1234/paper") == path
        True
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_root()
        self.files_dir = self.root / "files"
        self.db_path = self.root / "cache.db"

        self.files_dir.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    def _path_for(self, sha256: str) -> Path:
        return self.files_dir / f"{sha256}.pdf"

    def pdf(self, key: str) -> Path | None:
        """Path to the cached PDF, or None when absent."""
        row = self._conn.execute(
            "SELECT sha256 FROM documents WHERE key = ?", (normalize_key(key),)
        ).fetchone()
        if row is None:
            return None
        path = self._path_for(row[0])
        return path if path.exists() else None

    def source(self, key: str) -> str | None:
        """Downloader that provided the cached PDF, or None when absent."""
        row = self._conn.execute(
            "SELECT source FROM documents WHERE key = ?", (normalize_key(key),)
        ).fetchone()
        return row[0] if row else None

    def save_pdf(self, key: str, content: bytes, source: str) -> Path:
        """Store PDF bytes and return their path.

        The file is written before the row, so an interrupted save leaves at
        most an unreferenced file, which ``gc`` collects.
        """
        key = normalize_key(key)
        sha256 = hashlib.sha256(content).hexdigest()
        path = self._path_for(sha256)

        if not path.exists():
            fd, temp = tempfile.mkstemp(dir=self.files_dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
                os.replace(temp, path)
            except BaseException:
                Path(temp).unlink(missing_ok=True)
                raise

        self._conn.execute(
            "INSERT INTO documents (key, sha256, size, source, fetched_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "sha256 = excluded.sha256, size = excluded.size, "
            "source = excluded.source, fetched_at = excluded.fetched_at",
            (key, sha256, len(content), source, _now()),
        )
        self._conn.execute("DELETE FROM failures WHERE key = ?", (key,))

        return path

    def text(self, key: str, extractor: str | None = None) -> str | None:
        """Extracted text for a paper.

        Args:
            key: DOI or provider-specific id.
            extractor: When given, only return text produced by this extractor
                version, so a newer extractor re-extracts instead of reusing.
        """
        row = self._conn.execute(
            "SELECT content, extractor FROM texts WHERE key = ?", (normalize_key(key),)
        ).fetchone()
        if row is None:
            return None
        if extractor is not None and row[1] != extractor:
            return None
        return row[0]

    def save_text(self, key: str, content: str, extractor: str) -> None:
        """Store extracted text, replacing any previous extraction."""
        self._conn.execute(
            "INSERT INTO texts (key, extractor, content, extracted_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "extractor = excluded.extractor, content = excluded.content, "
            "extracted_at = excluded.extracted_at",
            (normalize_key(key), extractor, content, _now()),
        )

    def search(self, term: str, limit: int = 100) -> list[str]:
        """Keys whose extracted text matches an FTS5 query, best first."""
        rows = self._conn.execute(
            "SELECT t.key FROM texts_fts f JOIN texts t ON t.rowid = f.rowid "
            "WHERE texts_fts MATCH ? ORDER BY bm25(texts_fts) LIMIT ?",
            (term, limit),
        ).fetchall()
        return [row[0] for row in rows]

    def response(self, url: str, ttl: timedelta = DEFAULT_RESPONSE_TTL) -> tuple[bytes, str] | None:
        """Cached body and content type for a URL, or None when absent or stale."""
        row = self._conn.execute(
            "SELECT body, content_type, fetched_at FROM responses WHERE url = ?", (url,)
        ).fetchone()
        if row is None:
            return None
        if datetime.fromisoformat(row[2]) <= datetime.now(UTC) - ttl:
            return None
        return row[0], row[1] or ""

    def save_response(self, url: str, body: bytes, content_type: str | None) -> None:
        """Store an API response."""
        self._conn.execute(
            "INSERT INTO responses (url, body, content_type, fetched_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(url) DO UPDATE SET body = excluded.body, "
            "content_type = excluded.content_type, fetched_at = excluded.fetched_at",
            (url, body, content_type, _now()),
        )

    def expire_responses(self, ttl: timedelta = DEFAULT_RESPONSE_TTL) -> int:
        """Drop responses older than ``ttl``. Returns how many were dropped."""
        cutoff = (datetime.now(UTC) - ttl).isoformat()
        cursor = self._conn.execute("DELETE FROM responses WHERE fetched_at <= ?", (cutoff,))
        return cursor.rowcount

    def record_failure(self, key: str, error: str) -> None:
        """Remember that downloading a paper failed."""
        self._conn.execute(
            "INSERT INTO failures (key, error, failed_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET error = excluded.error, failed_at = excluded.failed_at",
            (normalize_key(key), error, _now()),
        )

    def failed_recently(self, key: str, ttl: timedelta = DEFAULT_FAILURE_TTL) -> bool:
        """Whether a download failed within ``ttl``, so retrying can be skipped."""
        row = self._conn.execute(
            "SELECT failed_at FROM failures WHERE key = ?", (normalize_key(key),)
        ).fetchone()
        if row is None:
            return False
        return datetime.fromisoformat(row[0]) > datetime.now(UTC) - ttl

    def stats(self) -> CacheStats:
        """Counts of what the cache holds, plus bytes of PDF on disk."""
        documents, total_bytes = self._conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(size), 0) FROM documents"
        ).fetchone()
        texts = self._conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
        responses = self._conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
        failures = self._conn.execute("SELECT COUNT(*) FROM failures").fetchone()[0]
        return CacheStats(
            documents=documents,
            texts=texts,
            responses=responses,
            failures=failures,
            bytes=total_bytes,
        )

    def gc(self, response_ttl: timedelta = DEFAULT_RESPONSE_TTL) -> GcReport:
        """Drop dangling rows, delete unreferenced files, expire stale responses."""
        referenced: set[str] = set()
        dropped = 0

        for key, sha256 in self._conn.execute("SELECT key, sha256 FROM documents").fetchall():
            if self._path_for(sha256).exists():
                referenced.add(sha256)
            else:
                self._conn.execute("DELETE FROM documents WHERE key = ?", (key,))
                dropped += 1

        deleted = 0
        for path in self.files_dir.iterdir():
            if path.suffix == ".tmp" or (path.suffix == ".pdf" and path.stem not in referenced):
                path.unlink()
                deleted += 1

        return GcReport(
            dropped_rows=dropped,
            deleted_files=deleted,
            expired_responses=self.expire_responses(response_ttl),
        )

    def clear(self) -> None:
        """Remove everything from the cache."""
        self._conn.execute("DELETE FROM documents")
        self._conn.execute("DELETE FROM texts")
        self._conn.execute("DELETE FROM responses")
        self._conn.execute("DELETE FROM failures")
        for path in self.files_dir.iterdir():
            path.unlink()


def _now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "Cache",
    "CacheStats",
    "DEFAULT_FAILURE_TTL",
    "DEFAULT_RESPONSE_TTL",
    "GcReport",
    "default_root",
    "key_to_doi",
    "normalize_key",
    "paper_key",
]
