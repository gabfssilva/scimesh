# tests/test_integration.py
import pytest

from scimesh import author, search, title, year
from scimesh.export import get_exporter
from scimesh.providers import Arxiv, OpenAlex, Scopus


@pytest.mark.asyncio
async def test_full_workflow_with_combinators():
    """Test full search workflow with combinators API."""
    q = title("attention") & author("Vaswani") & year(2017, 2020)

    result = await search(
        q,
        providers=[Arxiv(), OpenAlex()],
        on_error="ignore",
    )

    assert result.papers is not None
    # May be 0 if network fails, but structure should be correct
    assert isinstance(result.total_by_provider, dict)


@pytest.mark.asyncio
async def test_full_workflow_with_string_query():
    """Test full search workflow with Scopus string query."""
    result = await search(
        "TITLE(attention) AND AUTHOR(Vaswani)",
        providers=[Arxiv()],
        on_error="ignore",
    )

    assert result.papers is not None


def test_export_workflow():
    """Test that export produces valid output for all formats."""
    from scimesh.models import Author, Paper, SearchResult

    result = SearchResult(
        papers=[
            Paper(
                title="Test Paper",
                authors=(Author(name="Test Author"),),
                year=2020,
                source="test",
            )
        ],
        total_by_provider={"test": 1},
    )

    for fmt in ["csv", "json", "bibtex", "ris"]:
        exporter = get_exporter(fmt)
        output = exporter.to_string(result)
        assert len(output) > 0
        assert "Test Paper" in output or "Test" in output


def test_query_parsing_roundtrip():
    """Test that parsed queries work correctly."""
    from scimesh.query import author, parse, title

    # These should produce equivalent behavior
    q1 = parse("TITLE(transformer) AND AUTHOR(Vaswani)")
    q2 = title("transformer") & author("Vaswani")

    # Both should be valid Query objects that can be used
    assert q1 is not None
    assert q2 is not None


def test_provider_translation_consistency():
    """Test that all providers can translate the same query."""
    from scimesh.providers import Arxiv, OpenAlex
    from scimesh.query import author, title

    q = title("neural networks") & author("Hinton")

    arxiv = Arxiv()
    openalex = OpenAlex()
    scopus = Scopus()

    # All providers should translate without errors
    arxiv_query = arxiv._translate_query(q)
    openalex_search, openalex_filters = openalex._build_params(q)
    scopus_query = scopus._translate_query(q)

    assert arxiv_query  # non-empty string
    assert openalex_search or openalex_filters  # at least one should be non-empty
    assert scopus_query

    # Each should have their characteristic syntax
    assert "ti:" in arxiv_query or "au:" in arxiv_query
    assert "neural networks" in openalex_search or "raw_author_name" in openalex_filters.lower()
    assert "TITLE(" in scopus_query or "AUTH(" in scopus_query


def test_all_providers_have_pagination_support():
    """Verify all providers have pagination attributes."""
    from scimesh.providers import Arxiv, CrossRef, OpenAlex, Scopus, SemanticScholar

    # arXiv: offset-based with rate limiting
    assert hasattr(Arxiv, "PAGE_SIZE")
    assert hasattr(Arxiv, "RATE_LIMIT_DELAY")
    assert hasattr(Arxiv, "MAX_RESULTS")
    assert Arxiv.PAGE_SIZE == 100
    assert Arxiv.RATE_LIMIT_DELAY == 3.0
    assert Arxiv.MAX_RESULTS == 30000

    # Scopus: cursor-based
    assert hasattr(Scopus, "PAGE_SIZE")
    assert Scopus.PAGE_SIZE == 25

    # CrossRef: cursor-based
    assert hasattr(CrossRef, "PAGE_SIZE")
    assert CrossRef.PAGE_SIZE == 1000

    # Semantic Scholar: offset-based with limit
    assert hasattr(SemanticScholar, "PAGE_SIZE")
    assert hasattr(SemanticScholar, "MAX_TOTAL_RESULTS")
    assert SemanticScholar.PAGE_SIZE == 100
    assert SemanticScholar.MAX_TOTAL_RESULTS == 1000

    # OpenAlex: already has pagination (cursor-based)
    # Just verify it exists and has a consistent pattern
    assert OpenAlex.MAX_OR_TERMS == 10  # existing constant
