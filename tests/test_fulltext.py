# tests/test_fulltext.py
"""Tests for the fulltext search module."""

import pytest

from scimesh.fulltext import FulltextIndex


class TestFulltextIndex:
    """Tests for FulltextIndex class."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database path."""
        return tmp_path / "test_fulltext.db"

    @pytest.fixture
    def index(self, temp_db):
        """Create a FulltextIndex with temporary database."""
        return FulltextIndex(db_path=temp_db)

    def test_init_creates_database(self, temp_db):
        """Test that initialization creates the database file."""
        assert not temp_db.exists()
        FulltextIndex(db_path=temp_db)
        assert temp_db.exists()

    def test_add_and_search(self, index):
        """Test adding content and searching for it."""
        index.add("10.1234/paper1", "This is a paper about machine learning.")
        index.add("10.1234/paper2", "This paper discusses deep learning models.")

        results = index.search("machine learning")
        assert "10.1234/paper1" in results

        results = index.search("deep learning")
        assert "10.1234/paper2" in results

    def test_search_no_results(self, index):
        """Test search returns empty list when no matches."""
        index.add("10.1234/paper1", "Content about biology.")
        results = index.search("quantum physics")
        assert results == []

    def test_has_paper(self, index):
        """Test checking if paper exists in index."""
        assert not index.has("10.1234/paper1")
        index.add("10.1234/paper1", "Some content")
        assert index.has("10.1234/paper1")

    def test_remove_paper(self, index):
        """Test removing a paper from the index."""
        index.add("10.1234/paper1", "Some content")
        assert index.has("10.1234/paper1")

        result = index.remove("10.1234/paper1")
        assert result is True
        assert not index.has("10.1234/paper1")

    def test_remove_nonexistent(self, index):
        """Test removing a paper that doesn't exist."""
        result = index.remove("10.1234/nonexistent")
        assert result is False

    def test_count(self, index):
        """Test counting indexed papers."""
        assert index.count() == 0

        index.add("10.1234/paper1", "Content 1")
        assert index.count() == 1

        index.add("10.1234/paper2", "Content 2")
        assert index.count() == 2

    def test_clear(self, index):
        """Test clearing all indexed content."""
        index.add("10.1234/paper1", "Content 1")
        index.add("10.1234/paper2", "Content 2")
        assert index.count() == 2

        index.clear()
        assert index.count() == 0

    def test_list_papers(self, index):
        """Test listing indexed paper IDs."""
        index.add("10.1234/paper1", "Content 1")
        index.add("10.1234/paper2", "Content 2")

        papers = index.list_papers()
        assert len(papers) == 2
        assert "10.1234/paper1" in papers
        assert "10.1234/paper2" in papers

    def test_update_existing_paper(self, index):
        """Test updating content for existing paper."""
        index.add("10.1234/paper1", "Original content about biology.")
        results = index.search("biology")
        assert "10.1234/paper1" in results

        # Update with new content
        index.add("10.1234/paper1", "Updated content about chemistry.")
        results = index.search("chemistry")
        assert "10.1234/paper1" in results

        # Old content should not match anymore
        results = index.search("biology")
        assert "10.1234/paper1" not in results

    def test_skip_unchanged_content(self, index):
        """Test that unchanged content is not re-indexed."""
        content = "Some paper content"
        index.add("10.1234/paper1", content)

        # Get initial count
        assert index.count() == 1

        # Add same content again - should be skipped
        index.add("10.1234/paper1", content)
        assert index.count() == 1

    def test_search_limit(self, index):
        """Test search respects limit parameter."""
        for i in range(10):
            index.add(f"10.1234/paper{i}", f"Content about topic {i} and science")

        results = index.search("science", limit=5)
        assert len(results) <= 5

    def test_fts5_syntax(self, index):
        """Test that FTS5 syntax works in queries."""
        index.add("10.1234/paper1", "Machine learning and neural networks")
        index.add("10.1234/paper2", "Deep learning models")
        index.add("10.1234/paper3", "Statistical learning theory")

        # Phrase search
        results = index.search('"machine learning"')
        assert "10.1234/paper1" in results

        # OR search
        results = index.search("deep OR statistical")
        assert len(results) >= 2


class TestExtractTextFromPdf:
    """Tests for PDF text extraction."""

    def test_extract_nonexistent_file(self, tmp_path):
        """Test extraction from non-existent file returns None."""
        from scimesh.fulltext import extract_text_from_pdf

        result = extract_text_from_pdf(tmp_path / "nonexistent.pdf")
        assert result is None

    def test_extract_invalid_file(self, tmp_path):
        """Test extraction from invalid PDF returns None."""
        from scimesh.fulltext import extract_text_from_pdf

        # Create a file that's not a valid PDF
        invalid_pdf = tmp_path / "invalid.pdf"
        invalid_pdf.write_text("This is not a PDF")

        result = extract_text_from_pdf(invalid_pdf)
        # Should return None since it can't extract text
        assert result is None
