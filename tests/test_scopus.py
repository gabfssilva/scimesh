# tests/test_scopus.py
from scimesh.providers.scopus import Scopus
from scimesh.query.combinators import abstract, author, doi, fulltext, keyword, title, year


def test_translate_title():
    provider = Scopus()
    q = title("transformer")
    result = provider._translate_query(q)
    assert result == "TITLE(transformer)"


def test_translate_author():
    provider = Scopus()
    q = author("Vaswani")
    result = provider._translate_query(q)
    assert result == "AUTH(Vaswani)"


def test_translate_abstract():
    provider = Scopus()
    q = abstract("attention mechanism")
    result = provider._translate_query(q)
    assert result == "ABS(attention mechanism)"


def test_translate_keyword():
    provider = Scopus()
    q = keyword("machine learning")
    result = provider._translate_query(q)
    assert result == "KEY(machine learning)"


def test_translate_fulltext():
    provider = Scopus()
    q = fulltext("neural network")
    result = provider._translate_query(q)
    assert result == "ALL(neural network)"


def test_translate_doi():
    provider = Scopus()
    q = doi("10.1234/example")
    result = provider._translate_query(q)
    assert result == "DOI(10.1234/example)"


def test_translate_and():
    provider = Scopus()
    q = title("BERT") & author("Google")
    result = provider._translate_query(q)
    assert result == "(TITLE(BERT) AND AUTH(Google))"


def test_translate_or():
    provider = Scopus()
    q = title("BERT") | title("GPT")
    result = provider._translate_query(q)
    assert result == "(TITLE(BERT) OR TITLE(GPT))"


def test_translate_not():
    provider = Scopus()
    q = ~title("survey")
    result = provider._translate_query(q)
    assert result == "NOT TITLE(survey)"


def test_translate_year_range():
    provider = Scopus()
    q = year(2020, 2024)
    result = provider._translate_query(q)
    assert "PUBYEAR" in result
    # Should include years 2020-2024 inclusive
    assert "PUBYEAR > 2019" in result
    assert "PUBYEAR < 2025" in result


def test_translate_year_single():
    provider = Scopus()
    q = year(2023, 2023)
    result = provider._translate_query(q)
    assert result == "PUBYEAR = 2023"


def test_translate_year_start_only():
    provider = Scopus()
    q = year(start=2020)
    result = provider._translate_query(q)
    assert result == "PUBYEAR > 2019"


def test_translate_year_end_only():
    provider = Scopus()
    q = year(end=2024)
    result = provider._translate_query(q)
    assert result == "PUBYEAR < 2025"


def test_translate_complex_query():
    provider = Scopus()
    q = (title("deep learning") & author("LeCun")) | keyword("CNN")
    result = provider._translate_query(q)
    assert "TITLE(deep learning)" in result
    assert "AUTH(LeCun)" in result
    assert "KEY(CNN)" in result
    assert "AND" in result
    assert "OR" in result


def test_loads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("SCOPUS_API_KEY", "test-key-123")
    provider = Scopus()
    assert provider._api_key == "test-key-123"


def test_explicit_api_key_overrides_env(monkeypatch):
    monkeypatch.setenv("SCOPUS_API_KEY", "env-key")
    provider = Scopus(api_key="explicit-key")
    assert provider._api_key == "explicit-key"


def test_no_api_key_returns_none():
    # Clear any existing env var
    import os

    original = os.environ.pop("SCOPUS_API_KEY", None)
    try:
        provider = Scopus()
        assert provider._api_key is None
    finally:
        if original:
            os.environ["SCOPUS_API_KEY"] = original


def test_provider_name():
    provider = Scopus()
    assert provider.name == "scopus"


def test_base_url():
    provider = Scopus()
    assert provider.BASE_URL == "https://api.elsevier.com/content/search/scopus"
