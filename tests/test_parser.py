# tests/test_parser.py
from scimesh.query.combinators import And, Field, Not, Or, YearRange
from scimesh.query.parser import parse


def test_parse_simple_title():
    q = parse("TITLE(transformer)")
    assert q == Field("title", "transformer")


def test_parse_title_abs_key():
    q = parse("TITLE-ABS-KEY(machine learning)")
    assert isinstance(q, Or)
    # Should expand to title OR abstract OR keyword


def test_parse_author():
    q = parse("AUTHOR(Bengio)")
    assert q == Field("author", "Bengio")


def test_parse_and():
    q = parse("TITLE(transformer) AND AUTHOR(Vaswani)")
    assert isinstance(q, And)
    assert q.left == Field("title", "transformer")
    assert q.right == Field("author", "Vaswani")


def test_parse_or():
    q = parse("TITLE(BERT) OR TITLE(GPT)")
    assert isinstance(q, Or)


def test_parse_and_not():
    q = parse("TITLE(neural) AND NOT AUTHOR(Smith)")
    assert isinstance(q, And)
    assert isinstance(q.right, Not)


def test_parse_pubyear_equals():
    q = parse("PUBYEAR = 2020")
    assert q == YearRange(start=2020, end=2020)


def test_parse_pubyear_greater():
    q = parse("PUBYEAR > 2020")
    assert q == YearRange(start=2021, end=None)


def test_parse_pubyear_less():
    q = parse("PUBYEAR < 2020")
    assert q == YearRange(start=None, end=2019)


def test_parse_pubyear_greater_equal():
    q = parse("PUBYEAR >= 2020")
    assert q == YearRange(start=2020, end=None)


def test_parse_pubyear_less_equal():
    q = parse("PUBYEAR <= 2020")
    assert q == YearRange(start=None, end=2020)


def test_parse_complex_query():
    q = parse("TITLE-ABS-KEY(deep learning) AND AUTHOR(Hinton) AND PUBYEAR > 2015")
    assert isinstance(q, And)


def test_parse_with_parentheses():
    q = parse("(TITLE(A) OR TITLE(B)) AND AUTHOR(C)")
    assert isinstance(q, And)
    assert isinstance(q.left, Or)


def test_parse_all_fulltext():
    q = parse("ALL(attention mechanism)")
    assert q == Field("fulltext", "attention mechanism")
