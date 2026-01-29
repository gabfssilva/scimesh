# tests/test_combinators.py
from scimesh.query.combinators import (
    And,
    CitationRange,
    Field,
    Not,
    Or,
    YearRange,
    author,
    citations,
    extract_citation_range,
    extract_fulltext_term,
    fulltext,
    has_fulltext,
    keyword,
    remove_citation_range,
    remove_fulltext,
    title,
    year,
)


def test_title_creates_field():
    q = title("transformer")
    assert isinstance(q, Field)
    assert q.field == "title"
    assert q.value == "transformer"


def test_and_operator():
    q = title("transformer") & author("Vaswani")
    assert isinstance(q, And)
    assert q.left == Field("title", "transformer")
    assert q.right == Field("author", "Vaswani")


def test_or_operator():
    q = title("transformer") | title("attention")
    assert isinstance(q, Or)
    assert q.left == Field("title", "transformer")
    assert q.right == Field("title", "attention")


def test_not_operator():
    q = ~author("Google")
    assert isinstance(q, Not)
    assert q.operand == Field("author", "Google")


def test_year_range():
    q = year(2020, 2024)
    assert isinstance(q, YearRange)
    assert q.start == 2020
    assert q.end == 2024


def test_complex_query():
    q = (title("BERT") | title("GPT")) & author("OpenAI") & ~keyword("deprecated") & year(2018)
    assert isinstance(q, And)


def test_query_is_hashable():
    q1 = title("test")
    q2 = title("test")
    assert hash(q1) == hash(q2)
    assert q1 == q2


# Tests for has_fulltext


def test_has_fulltext_simple():
    assert has_fulltext(fulltext("test"))
    assert not has_fulltext(title("test"))


def test_has_fulltext_in_and():
    q = title("transformer") & fulltext("attention")
    assert has_fulltext(q)


def test_has_fulltext_in_or():
    q = title("transformer") | fulltext("attention")
    assert has_fulltext(q)


def test_has_fulltext_in_not():
    q = ~fulltext("excluded")
    assert has_fulltext(q)


def test_has_fulltext_nested():
    q = (title("bert") & fulltext("nlp")) | author("google")
    assert has_fulltext(q)


def test_has_fulltext_none():
    q = title("bert") & author("google") & year(2020)
    assert not has_fulltext(q)


# Tests for extract_fulltext_term


def test_extract_fulltext_term_simple():
    assert extract_fulltext_term(fulltext("test term")) == "test term"


def test_extract_fulltext_term_in_and():
    q = title("transformer") & fulltext("attention mechanism")
    assert extract_fulltext_term(q) == "attention mechanism"


def test_extract_fulltext_term_in_or():
    q = fulltext("nlp") | title("bert")
    assert extract_fulltext_term(q) == "nlp"


def test_extract_fulltext_term_none():
    q = title("bert") & author("google")
    assert extract_fulltext_term(q) is None


# Tests for remove_fulltext


def test_remove_fulltext_simple():
    # Only fulltext returns None
    assert remove_fulltext(fulltext("test")) is None


def test_remove_fulltext_preserves_other():
    q = title("transformer")
    assert remove_fulltext(q) == q


def test_remove_fulltext_from_and():
    q = title("transformer") & fulltext("attention")
    result = remove_fulltext(q)
    assert result == title("transformer")


def test_remove_fulltext_from_and_both_sides():
    q = fulltext("a") & fulltext("b")
    assert remove_fulltext(q) is None


def test_remove_fulltext_from_or():
    q = fulltext("nlp") | title("bert")
    result = remove_fulltext(q)
    assert result == title("bert")


def test_remove_fulltext_from_not():
    q = ~fulltext("excluded")
    assert remove_fulltext(q) is None


def test_remove_fulltext_nested():
    q = (title("bert") & fulltext("nlp")) & author("google")
    result = remove_fulltext(q)
    assert result == And(title("bert"), author("google"))


def test_remove_fulltext_preserves_year():
    q = fulltext("test") & year(2020, 2023)
    result = remove_fulltext(q)
    assert result == year(2020, 2023)


# Tests for CitationRange and citations()


def test_citations_min_only():
    q = citations(100)
    assert isinstance(q, CitationRange)
    assert q.min == 100
    assert q.max is None


def test_citations_min_and_max():
    q = citations(100, 500)
    assert isinstance(q, CitationRange)
    assert q.min == 100
    assert q.max == 500


def test_citations_max_only():
    q = citations(max=200)
    assert isinstance(q, CitationRange)
    assert q.min is None
    assert q.max == 200


def test_citations_keyword_min():
    q = citations(min=50)
    assert isinstance(q, CitationRange)
    assert q.min == 50
    assert q.max is None


# Tests for extract_citation_range


def test_extract_citation_range_simple():
    q = citations(100)
    assert extract_citation_range(q) == CitationRange(min=100)


def test_extract_citation_range_in_and():
    q = title("transformer") & citations(50)
    result = extract_citation_range(q)
    assert result == CitationRange(min=50)


def test_extract_citation_range_none():
    q = title("bert") & author("google")
    assert extract_citation_range(q) is None


# Tests for remove_citation_range


def test_remove_citation_range_simple():
    assert remove_citation_range(citations(100)) is None


def test_remove_citation_range_preserves_other():
    q = title("transformer")
    assert remove_citation_range(q) == q


def test_remove_citation_range_from_and():
    q = title("transformer") & citations(100)
    result = remove_citation_range(q)
    assert result == title("transformer")


def test_remove_citation_range_nested():
    q = (title("bert") & citations(50)) & author("google")
    result = remove_citation_range(q)
    assert result == And(title("bert"), author("google"))
