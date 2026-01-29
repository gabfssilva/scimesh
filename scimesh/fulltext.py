# scimesh/fulltext.py
"""Fulltext search using SQLite FTS5."""

import sqlite3
from pathlib import Path


class FulltextIndex:
    """SQLite FTS5-based fulltext index for paper content.

    Stores extracted text from PDFs and allows fulltext search across
    indexed content.

    Attributes:
        db_path: Path to the SQLite database file.

    Example:
        >>> index = FulltextIndex()
        >>> index.add("10.1234/paper", "This is the paper content...")
        >>> results = index.search("paper content")
        >>> print(results)
        ['10.1234/paper']
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize the fulltext index.

        Args:
            db_path: Path to the SQLite database file.
                Defaults to ~/.scimesh/fulltext.db
        """
        self.db_path = db_path or Path.home() / ".scimesh" / "fulltext.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Create FTS5 virtual table for fulltext search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
                    paper_id,
                    content,
                    tokenize='porter unicode61'
                )
            """)
            # Create a regular table to track metadata
            conn.execute("""
                CREATE TABLE IF NOT EXISTS papers_meta (
                    paper_id TEXT PRIMARY KEY,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    content_hash TEXT
                )
            """)
            conn.commit()

    def add(self, paper_id: str, content: str) -> None:
        """Add or update a paper's content in the index.

        Args:
            paper_id: The DOI or paper identifier.
            content: The extracted text content.
        """
        import hashlib

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            # Check if paper exists and content has changed
            cursor = conn.execute(
                "SELECT content_hash FROM papers_meta WHERE paper_id = ?",
                (paper_id,),
            )
            row = cursor.fetchone()

            if row and row[0] == content_hash:
                # Content hasn't changed, skip
                return

            if row:
                # Update existing entry
                conn.execute(
                    "DELETE FROM papers_fts WHERE paper_id = ?",
                    (paper_id,),
                )
                conn.execute(
                    "UPDATE papers_meta SET content_hash = ?, indexed_at = CURRENT_TIMESTAMP "
                    "WHERE paper_id = ?",
                    (content_hash, paper_id),
                )
            else:
                # Insert new entry
                conn.execute(
                    "INSERT INTO papers_meta (paper_id, content_hash) VALUES (?, ?)",
                    (paper_id, content_hash),
                )

            # Insert content into FTS table
            conn.execute(
                "INSERT INTO papers_fts (paper_id, content) VALUES (?, ?)",
                (paper_id, content),
            )
            conn.commit()

    def search(self, query: str, limit: int = 100) -> list[str]:
        """Search the index for matching papers.

        Args:
            query: The search query (supports FTS5 syntax).
            limit: Maximum number of results to return.

        Returns:
            List of matching paper IDs, ordered by relevance.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Use FTS5's bm25 ranking function for relevance ordering
            cursor = conn.execute(
                """
                SELECT paper_id, bm25(papers_fts) as rank
                FROM papers_fts
                WHERE papers_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            return [row[0] for row in cursor.fetchall()]

    def has(self, paper_id: str) -> bool:
        """Check if a paper is in the index.

        Args:
            paper_id: The DOI or paper identifier.

        Returns:
            True if the paper is indexed, False otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM papers_meta WHERE paper_id = ?",
                (paper_id,),
            )
            return cursor.fetchone() is not None

    def remove(self, paper_id: str) -> bool:
        """Remove a paper from the index.

        Args:
            paper_id: The DOI or paper identifier.

        Returns:
            True if the paper was removed, False if it wasn't in the index.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM papers_fts WHERE paper_id = ?",
                (paper_id,),
            )
            conn.execute(
                "DELETE FROM papers_meta WHERE paper_id = ?",
                (paper_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def count(self) -> int:
        """Get the number of indexed papers.

        Returns:
            Number of papers in the index.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM papers_meta")
            return cursor.fetchone()[0]

    def clear(self) -> None:
        """Clear all indexed content."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM papers_fts")
            conn.execute("DELETE FROM papers_meta")
            conn.commit()

    def list_papers(self, limit: int = 1000) -> list[str]:
        """List all indexed paper IDs.

        Args:
            limit: Maximum number of IDs to return.

        Returns:
            List of paper IDs.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT paper_id FROM papers_meta ORDER BY indexed_at DESC LIMIT ?",
                (limit,),
            )
            return [row[0] for row in cursor.fetchall()]


def extract_text_from_pdf(pdf_path: Path) -> str | None:
    """Extract text from a PDF file.

    Attempts to use pdftotext (poppler) first, falls back to pypdf.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text, or None if extraction failed.
    """
    import subprocess

    # Try pdftotext first (faster and more accurate)
    try:
        result = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fall back to pypdf if available
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(pdf_path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts)
    except ImportError:
        pass
    except Exception:
        pass

    return None


__all__ = ["FulltextIndex", "extract_text_from_pdf"]
