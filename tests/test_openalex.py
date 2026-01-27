# tests/test_openalex.py
from scimesh.providers.openalex import OpenAlex
from scimesh.query.combinators import abstract, author, fulltext, keyword, title, year


def test_translate_title():
    provider = OpenAlex()
    q = title("transformer")
    search, filters = provider._build_params(q)
    assert "transformer" in search


def test_translate_author():
    provider = OpenAlex()
    q = author("Vaswani")
    search, filters = provider._build_params(q)
    assert "raw_author_name.search:Vaswani" in filters


def test_translate_abstract():
    provider = OpenAlex()
    q = abstract("attention mechanism")
    search, filters = provider._build_params(q)
    assert "attention mechanism" in search


def test_translate_keyword():
    provider = OpenAlex()
    q = keyword("machine learning")
    search, filters = provider._build_params(q)
    assert "machine learning" in search


def test_translate_fulltext():
    provider = OpenAlex()
    q = fulltext("neural network")
    search, filters = provider._build_params(q)
    # OpenAlex has native fulltext search via fulltext.search filter
    assert "fulltext.search:neural network" in filters


def test_translate_and():
    provider = OpenAlex()
    q = title("BERT") & author("Google")
    search, filters = provider._build_params(q)
    assert "BERT" in search
    assert "raw_author_name.search:Google" in filters


def test_translate_or():
    provider = OpenAlex()
    q = title("BERT") | title("GPT")
    search, filters = provider._build_params(q)
    assert "BERT" in search
    assert "GPT" in search


def test_translate_year_range():
    provider = OpenAlex()
    q = year(2020, 2024)
    search, filters = provider._build_params(q)
    assert "publication_year:2020-2024" in filters


def test_translate_year_single():
    provider = OpenAlex()
    q = year(2023, 2023)
    search, filters = provider._build_params(q)
    assert "publication_year:2023" in filters


def test_translate_year_start_only():
    provider = OpenAlex()
    q = year(start=2020)
    search, filters = provider._build_params(q)
    assert "publication_year:>2019" in filters


def test_translate_year_end_only():
    provider = OpenAlex()
    q = year(end=2024)
    search, filters = provider._build_params(q)
    assert "publication_year:<2025" in filters


def test_no_api_key_needed():
    provider = OpenAlex()
    assert provider._api_key is None


def test_reconstruct_abstract():
    provider = OpenAlex()
    inverted_index = {
        "The": [0],
        "quick": [1],
        "brown": [2],
        "fox": [3],
        "jumps": [4],
    }
    result = provider._reconstruct_abstract(inverted_index)
    assert result == "The quick brown fox jumps"


def test_reconstruct_abstract_multiple_occurrences():
    provider = OpenAlex()
    inverted_index = {
        "the": [0, 5],
        "cat": [1],
        "sat": [2],
        "on": [3],
        "mat": [4, 6],
    }
    result = provider._reconstruct_abstract(inverted_index)
    assert result == "the cat sat on mat the mat"
