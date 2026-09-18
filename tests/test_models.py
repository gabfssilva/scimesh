# tests/test_models.py
from scimesh.models import Author, Paper, SearchResult


def test_author_creation():
    author = Author(name="Yoshua Bengio", affiliation="Mila", orcid="0000-0001-1234-5678")
    assert author.name == "Yoshua Bengio"
    assert author.affiliation == "Mila"


def test_author_minimal():
    author = Author(name="John Doe")
    assert author.affiliation is None
    assert author.orcid is None


def test_paper_creation():
    paper = Paper(
        title="Attention Is All You Need",
        authors=(Author(name="Vaswani"),),
        year=2017,
        source="arxiv",
        doi="10.1234/test",
    )
    assert paper.title == "Attention Is All You Need"
    assert paper.year == 2017
    assert paper.source == "arxiv"


def test_paper_hash_by_doi():
    p1 = Paper(title="Test", authors=(), year=2020, source="arxiv", doi="10.1234/a")
    p2 = Paper(title="Different", authors=(), year=2021, source="scopus", doi="10.1234/a")
    assert hash(p1) == hash(p2)


def test_paper_hash_by_title_year():
    p1 = Paper(title="Test Paper", authors=(), year=2020, source="arxiv")
    p2 = Paper(title="Test Paper", authors=(), year=2020, source="scopus")
    assert hash(p1) == hash(p2)


def test_search_result_total_by_provider():
    result = SearchResult(
        papers=[],
        total_by_provider={"arxiv": 10},
    )
    assert result.total_by_provider["arxiv"] == 10
