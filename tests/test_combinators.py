# tests/test_combinators.py
from scimesh.query.combinators import (
    And,
    Field,
    Not,
    Or,
    YearRange,
    author,
    extract_fulltext_term,
    fulltext,
    has_fulltext,
    keyword,
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
