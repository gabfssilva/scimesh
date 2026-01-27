# tests/test_merge.py
import pytest

from scimesh.models import Author, Paper, SearchResult, merge_papers


class TestMergePapers:
    """Tests for merge_papers function."""

    def test_merge_abstracts_picks_longest(self):
        """Merging papers should pick the longest non-null abstract."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            abstract="Short",
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            abstract="This is a much longer abstract with more details",
        )
        p3 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="openalex",
            abstract=None,
        )

        merged = merge_papers([p1, p2, p3])

        assert merged.abstract == "This is a much longer abstract with more details"

    def test_merge_abstracts_handles_all_none(self):
        """When all abstracts are None, merged abstract should be None."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            abstract=None,
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            abstract=None,
        )

        merged = merge_papers([p1, p2])

        assert merged.abstract is None

    def test_merge_citation_counts_picks_highest(self):
        """Merging papers should pick the highest citation count."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            citations_count=10,
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            citations_count=150,
        )
        p3 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="openalex",
            citations_count=100,
        )

        merged = merge_papers([p1, p2, p3])

        assert merged.citations_count == 150

    def test_merge_citation_counts_handles_none(self):
        """When some citation counts are None, should pick highest non-null."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            citations_count=None,
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            citations_count=50,
        )

        merged = merge_papers([p1, p2])

        assert merged.citations_count == 50

    def test_merge_references_count_picks_highest(self):
        """Merging papers should pick the highest references count."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            references_count=20,
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            references_count=25,
        )

        merged = merge_papers([p1, p2])

        assert merged.references_count == 25

    def test_merge_topics_union(self):
        """Merging papers should create union of all topics."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            topics=("machine learning", "neural networks"),
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            topics=("deep learning", "neural networks"),
        )
        p3 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="openalex",
            topics=("AI", "machine learning"),
        )

        merged = merge_papers([p1, p2, p3])

        assert set(merged.topics) == {
            "machine learning",
            "neural networks",
            "deep learning",
            "AI",
        }
        # Topics should be sorted
        assert merged.topics == tuple(sorted(merged.topics))

    def test_merge_topics_empty(self):
        """When all topics are empty, merged topics should be empty."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            topics=(),
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            topics=(),
        )

        merged = merge_papers([p1, p2])

        assert merged.topics == ()

    def test_merge_authors_picks_most_entries(self):
        """Merging papers should pick the author list with most entries."""
        author1 = Author(name="Alice")
        author2 = Author(name="Bob")
        author3 = Author(name="Charlie")

        p1 = Paper(
            title="Test Paper",
            authors=(author1,),
            year=2020,
            source="arxiv",
        )
        p2 = Paper(
            title="Test Paper",
            authors=(author1, author2, author3),
            year=2020,
            source="scopus",
        )

        merged = merge_papers([p1, p2])

        assert len(merged.authors) == 3
        assert merged.authors == (author1, author2, author3)

    def test_merge_single_paper_returns_same(self):
        """Merging a single paper should return the same paper."""
        p = Paper(
            title="Test Paper",
            authors=(Author(name="Alice"),),
            year=2020,
            source="arxiv",
            doi="10.1234/test",
            abstract="Test abstract",
            citations_count=100,
        )

        merged = merge_papers([p])

        assert merged == p
        assert merged.title == p.title
        assert merged.source == p.source
        assert merged.abstract == p.abstract

    def test_merge_empty_list_raises_error(self):
        """Merging empty list should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot merge empty list"):
            merge_papers([])

    def test_merge_preserves_primary_source(self):
        """Merged paper should have source from first paper."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
        )

        merged = merge_papers([p1, p2])

        assert merged.source == "arxiv"

    def test_merge_first_non_null_fields(self):
        """Other fields should use first non-null value."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            doi=None,
            url="http://arxiv.org/paper",
            journal=None,
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            doi="10.1234/test",
            url="http://scopus.com/paper",
            journal="Nature",
        )

        merged = merge_papers([p1, p2])

        assert merged.doi == "10.1234/test"
        assert merged.url == "http://arxiv.org/paper"  # First non-null
        assert merged.journal == "Nature"

    def test_merge_open_access_true_if_any(self):
        """Open access should be True if any source says True."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            open_access=False,
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="openalex",
            open_access=True,
        )

        merged = merge_papers([p1, p2])

        assert merged.open_access is True

    def test_merge_extras_combines_without_conflict(self):
        """Extras should be combined when no conflicts exist."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            extras={"arxiv_id": "2020.12345", "category": "cs.AI"},
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            extras={"scopus_id": "12345", "eid": "2-s2.0-123"},
        )

        merged = merge_papers([p1, p2])

        assert merged.extras["arxiv_id"] == "2020.12345"
        assert merged.extras["category"] == "cs.AI"
        assert merged.extras["scopus_id"] == "12345"
        assert merged.extras["eid"] == "2-s2.0-123"

    def test_merge_extras_prefixes_on_conflict(self):
        """Extras with conflicting keys should be prefixed with source name."""
        p1 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="arxiv",
            extras={"id": "arxiv-123", "unique_to_arxiv": "value1"},
        )
        p2 = Paper(
            title="Test Paper",
            authors=(),
            year=2020,
            source="scopus",
            extras={"id": "scopus-456", "unique_to_scopus": "value2"},
        )

        merged = merge_papers([p1, p2])

        # First value wins for "id"
        assert merged.extras["id"] == "arxiv-123"
        # Conflicting value gets prefixed
        assert merged.extras["scopus_id"] == "scopus-456"
        # Non-conflicting values are kept
        assert merged.extras["unique_to_arxiv"] == "value1"
        assert merged.extras["unique_to_scopus"] == "value2"


class TestSearchResultDedupeWithMerge:
    """Tests for SearchResult.dedupe() with merge functionality."""

    def test_dedupe_merges_duplicates_by_doi(self):
        """Dedupe should merge papers with same DOI."""
        papers = [
            Paper(
                title="Paper A",
                authors=(),
                year=2020,
                source="arxiv",
                doi="10.1/a",
                abstract="Short",
                citations_count=10,
            ),
            Paper(
                title="Paper A Copy",
                authors=(),
                year=2020,
                source="scopus",
                doi="10.1/a",
                abstract="Much longer abstract here",
                citations_count=50,
            ),
            Paper(
                title="Paper B",
                authors=(),
                year=2021,
                source="arxiv",
                doi="10.1/b",
            ),
        ]

        result = SearchResult(papers=papers)
        deduped = result.dedupe()

        assert len(deduped.papers) == 2

        # Find the merged paper A
        paper_a = next(p for p in deduped.papers if p.doi == "10.1/a")
        assert paper_a.abstract == "Much longer abstract here"
        assert paper_a.citations_count == 50
        assert paper_a.source == "arxiv"  # Primary source

    def test_dedupe_merges_duplicates_by_title_year(self):
        """Dedupe should merge papers with same title and year (no DOI)."""
        papers = [
            Paper(
                title="Test Paper",
                authors=(Author(name="Alice"),),
                year=2020,
                source="arxiv",
                topics=("ML",),
            ),
            Paper(
                title="Test Paper",
                authors=(Author(name="Alice"), Author(name="Bob")),
                year=2020,
                source="openalex",
                topics=("AI",),
            ),
        ]

        result = SearchResult(papers=papers)
        deduped = result.dedupe()

        assert len(deduped.papers) == 1

        merged = deduped.papers[0]
        assert len(merged.authors) == 2  # More authors
        assert set(merged.topics) == {"ML", "AI"}  # Union

    def test_dedupe_preserves_unique_papers(self):
        """Dedupe should not modify papers that have no duplicates."""
        p = Paper(
            title="Unique Paper",
            authors=(Author(name="Alice"),),
            year=2020,
            source="arxiv",
            doi="10.1/unique",
            abstract="Unique abstract",
        )

        result = SearchResult(papers=[p])
        deduped = result.dedupe()

        assert len(deduped.papers) == 1
        assert deduped.papers[0] == p

    def test_dedupe_preserves_metadata(self):
        """Dedupe should preserve total_by_provider."""
        papers = [
            Paper(title="A", authors=(), year=2020, source="arxiv"),
        ]
        totals = {"arxiv": 10, "scopus": 0}

        result = SearchResult(papers=papers, total_by_provider=totals)
        deduped = result.dedupe()

        assert deduped.total_by_provider == totals
