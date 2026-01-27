# tests/test_combinators.py
from scimesh.query.combinators import (
    And,
    Field,
    Not,
    Or,
    YearRange,
    author,
    keyword,
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
