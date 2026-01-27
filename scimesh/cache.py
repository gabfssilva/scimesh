# scimesh/cache.py
"""PDF caching system for scimesh.

Provides thread-safe caching of downloaded PDFs and extracted text content.
"""

import hashlib
import os
import re
import tempfile
from pathlib import Path


class PaperCache:
    """Thread-safe cache for PDFs and extracted text.

    Stores PDFs and extracted text in a local directory structure.
    Uses atomic writes (write to temp file, then rename) for thread safety.

    Attributes:
        cache_dir: Root directory for all cached files.
        pdf_dir: Directory for cached PDF files.
        text_dir: Directory for cached extracted text files.

    Example:
        >>> cache = PaperCache()
        >>> cache.save_pdf("10.1234/paper", b"%PDF-1.4...")
        PosixPath('/Users/.../.scimesh/cache/pdfs/10.1234_paper.pdf')
        >>> cache.has_pdf("10.1234/paper")
        True
        >>> pdf_path = cache.get_pdf_path("10.1234/paper")
    """

    def __init__(self, cache_dir: Path | None = None):
        """Initialize the paper cache.

        Args:
            cache_dir: Root directory for cache storage.
                Defaults to ~/.scimesh/cache
        """
        self.cache_dir = cache_dir or Path.home() / ".scimesh" / "cache"
        self.pdf_dir = self.cache_dir / "pdfs"
        self.text_dir = self.cache_dir / "text"

        # Create directories on init
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.text_dir.mkdir(parents=True, exist_ok=True)

    def _make_safe_filename(self, paper_id: str) -> str:
        """Convert DOI/ID to safe filename.

        Replaces invalid filesystem characters with safe alternatives.
        For very long IDs, uses a hash to avoid filesystem limits.

        Args:
            paper_id: The DOI or paper identifier.

        Returns:
            A filesystem-safe filename (without extension).

        Example:
            >>> cache = PaperCache()
            >>> cache._make_safe_filename("10.1234/paper.v1")
            '10.1234_paper.v1'
        """
        # Replace / with _
        filename = paper_id.replace("/", "_")

        # Replace other invalid characters: \ : * ? " < > |
        invalid_chars = r'[\\:*?"<>|]'
        filename = re.sub(invalid_chars, "_", filename)

        # If filename is too long (common limit is 255), use hash
        if len(filename) > 200:
            hash_suffix = hashlib.sha256(paper_id.encode()).hexdigest()[:16]
            filename = filename[:180] + "_" + hash_suffix

        return filename

    def has_pdf(self, paper_id: str) -> bool:
        """Check if PDF exists in cache.

        Args:
            paper_id: The DOI or paper identifier.

        Returns:
            True if the PDF is cached, False otherwise.
        """
        filename = self._make_safe_filename(paper_id) + ".pdf"
        return (self.pdf_dir / filename).exists()

    def get_pdf_path(self, paper_id: str) -> Path | None:
        """Get path to cached PDF if exists.

        Args:
            paper_id: The DOI or paper identifier.

        Returns:
            Path to the cached PDF file, or None if not cached.
        """
        filename = self._make_safe_filename(paper_id) + ".pdf"
        path = self.pdf_dir / filename
        return path if path.exists() else None

    def save_pdf(self, paper_id: str, content: bytes) -> Path:
        """Save PDF to cache, return path.

        Uses atomic write (write to temp file, then rename) for thread safety.

        Args:
            paper_id: The DOI or paper identifier.
            content: The PDF file content as bytes.

        Returns:
            Path to the saved PDF file.
        """
        filename = self._make_safe_filename(paper_id) + ".pdf"
        target_path = self.pdf_dir / filename

        # Atomic write: write to temp file in same directory, then rename
        fd, temp_path = tempfile.mkstemp(dir=self.pdf_dir, suffix=".tmp")
        try:
            os.write(fd, content)
            os.close(fd)
            # Atomic rename on POSIX systems
            os.replace(temp_path, target_path)
        except Exception:
            # Clean up temp file on error
            os.close(fd) if fd else None
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        return target_path

    def has_text(self, paper_id: str) -> bool:
        """Check if extracted text exists.

        Args:
            paper_id: The DOI or paper identifier.

        Returns:
            True if the extracted text is cached, False otherwise.
        """
        filename = self._make_safe_filename(paper_id) + ".txt"
        return (self.text_dir / filename).exists()

    def get_text(self, paper_id: str) -> str | None:
        """Get cached extracted text.

        Args:
            paper_id: The DOI or paper identifier.

        Returns:
            The extracted text content, or None if not cached.
        """
        filename = self._make_safe_filename(paper_id) + ".txt"
        path = self.text_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def save_text(self, paper_id: str, text: str) -> Path:
        """Save extracted text to cache.

        Uses atomic write (write to temp file, then rename) for thread safety.

        Args:
            paper_id: The DOI or paper identifier.
            text: The extracted text content.

        Returns:
            Path to the saved text file.
        """
        filename = self._make_safe_filename(paper_id) + ".txt"
        target_path = self.text_dir / filename

        # Atomic write: write to temp file in same directory, then rename
        fd, temp_path = tempfile.mkstemp(dir=self.text_dir, suffix=".tmp")
        try:
            os.write(fd, text.encode("utf-8"))
            os.close(fd)
            # Atomic rename on POSIX systems
            os.replace(temp_path, target_path)
        except Exception:
            # Clean up temp file on error
            os.close(fd) if fd else None
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        return target_path

    def clear(self) -> None:
        """Clear all cached files.

        Removes all PDFs and text files from the cache directories.
        Does not remove the directories themselves.
        """
        # Clear PDFs
        for pdf_file in self.pdf_dir.glob("*.pdf"):
            pdf_file.unlink()

        # Clear temp files
        for tmp_file in self.pdf_dir.glob("*.tmp"):
            tmp_file.unlink()

        # Clear text files
        for text_file in self.text_dir.glob("*.txt"):
            text_file.unlink()

        # Clear temp files in text dir
        for tmp_file in self.text_dir.glob("*.tmp"):
            tmp_file.unlink()


__all__ = ["PaperCache"]
