# tests/test_arxiv.py
from scimesh.providers.arxiv import Arxiv
from scimesh.query.combinators import abstract, author, fulltext, title, year


def test_translate_title():
    provider = Arxiv()
    q = title("transformer")
    result = provider._translate_query(q)
    assert result == 'ti:"transformer"'


def test_translate_author():
    provider = Arxiv()
    q = author("Vaswani")
    result = provider._translate_query(q)
    assert result == 'au:"Vaswani"'


def test_translate_abstract():
    provider = Arxiv()
    q = abstract("attention mechanism")
    result = provider._translate_query(q)
    assert result == 'abs:"attention mechanism"'


def test_translate_fulltext():
    provider = Arxiv()
    q = fulltext("neural network")
    result = provider._translate_query(q)
    assert result == 'all:"neural network"'


def test_translate_and():
    provider = Arxiv()
    q = title("BERT") & author("Google")
    result = provider._translate_query(q)
    assert result == '(ti:"BERT" AND au:"Google")'


def test_translate_or():
    provider = Arxiv()
    q = title("BERT") | title("GPT")
    result = provider._translate_query(q)
    assert result == '(ti:"BERT" OR ti:"GPT")'


def test_translate_not():
    provider = Arxiv()
    q = title("neural") & ~author("Smith")
    result = provider._translate_query(q)
    assert result == '(ti:"neural" ANDNOT au:"Smith")'


def test_translate_year_ignored():
    provider = Arxiv()
    q = year(2020, 2024)
    result = provider._translate_query(q)
    assert result == ""  # arXiv doesn't support year in query


def test_no_api_key_needed():
    provider = Arxiv()
    assert provider._api_key is None
