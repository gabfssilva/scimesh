# tests/test_parser.py
from scimesh.query.combinators import And, CitationRange, Field, Not, Or, YearRange
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


def test_parse_plain_text():
    """Plain text without field specifier searches title and abstract."""
    q = parse("transformers")
    assert isinstance(q, Or)
    assert q.left == Field("title", "transformers")
    assert q.right == Field("abstract", "transformers")


def test_parse_plain_text_multi_word():
    """Multi-word plain text."""
    q = parse("attention mechanism")
    assert isinstance(q, Or)
    assert q.left == Field("title", "attention mechanism")
    assert q.right == Field("abstract", "attention mechanism")


def test_parse_plain_text_with_and():
    """Plain text combined with field specifier."""
    q = parse("transformers AND AUTHOR(Vaswani)")
    assert isinstance(q, And)
    assert isinstance(q.left, Or)  # title OR abstract
    assert q.right == Field("author", "Vaswani")


def test_parse_plain_text_with_year():
    """Plain text with year filter."""
    q = parse("deep learning AND PUBYEAR > 2020")
    assert isinstance(q, And)
    assert isinstance(q.left, Or)  # title OR abstract
    assert q.right == YearRange(start=2021, end=None)


def test_parse_title_with_or_inside():
    """TITLE with OR inside should expand to OR of Fields."""
    q = parse('TITLE("deep learning" OR "neural network")')
    assert isinstance(q, Or)
    assert q.left == Field("title", "deep learning")
    assert q.right == Field("title", "neural network")


def test_parse_title_abs_with_or_inside():
    """TITLE-ABS with OR inside should expand properly.

    TITLE-ABS("a" OR "b") should become:
    Or(
        Or(Field(title, "a"), Field(abstract, "a")),
        Or(Field(title, "b"), Field(abstract, "b"))
    )
    """
    q = parse('TITLE-ABS("deep learning" OR imputation)')
    assert isinstance(q, Or)
    # Left side: TITLE-ABS("deep learning")
    assert isinstance(q.left, Or)
    assert q.left.left == Field("title", "deep learning")
    assert q.left.right == Field("abstract", "deep learning")
    # Right side: TITLE-ABS(imputation)
    assert isinstance(q.right, Or)
    assert q.right.left == Field("title", "imputation")
    assert q.right.right == Field("abstract", "imputation")


def test_parse_title_abs_with_multiple_or_inside():
    """TITLE-ABS with multiple OR terms."""
    q = parse("TITLE-ABS(a OR b OR c)")
    # Should be: Or(Or(TITLE-ABS(a), TITLE-ABS(b)), TITLE-ABS(c))
    assert isinstance(q, Or)
    # The structure is left-associative: ((a OR b) OR c)


def test_parse_complex_query_with_or_inside_title_abs():
    """Complex query with OR inside TITLE-ABS and AND between clauses."""
    query = (
        'TITLE-ABS("deep learning" OR "neural network") '
        "AND TITLE-ABS(imputation) AND PUBYEAR > 2019"
    )
    q = parse(query)
    assert isinstance(q, And)
    # Should have year range on the right
    assert q.right == YearRange(start=2020, end=None)


# Tests for CITEDBY/CITATIONS


def test_parse_citedby_equals():
    q = parse("CITEDBY = 100")
    assert q == CitationRange(min=100, max=100)


def test_parse_citedby_greater():
    q = parse("CITEDBY > 50")
    assert q == CitationRange(min=51, max=None)


def test_parse_citedby_greater_equal():
    q = parse("CITEDBY >= 100")
    assert q == CitationRange(min=100, max=None)


def test_parse_citedby_less():
    q = parse("CITEDBY < 100")
    assert q == CitationRange(min=None, max=99)


def test_parse_citedby_less_equal():
    q = parse("CITEDBY <= 100")
    assert q == CitationRange(min=None, max=100)


def test_parse_citations_alias():
    """CITATIONS should work as alias for CITEDBY."""
    q = parse("CITATIONS >= 50")
    assert q == CitationRange(min=50, max=None)


def test_parse_citedby_with_title():
    q = parse("TITLE(deep learning) AND CITEDBY >= 100")
    assert isinstance(q, And)
    assert q.left == Field("title", "deep learning")
    assert q.right == CitationRange(min=100, max=None)


def test_parse_citedby_with_pubyear():
    q = parse("TITLE(ml) AND PUBYEAR > 2020 AND CITEDBY >= 50")
    assert isinstance(q, And)
