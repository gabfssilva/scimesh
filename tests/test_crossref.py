# tests/test_crossref.py
import os

from scimesh.providers.crossref import CrossRef
from scimesh.query.combinators import abstract, author, doi, fulltext, keyword, title, year


def test_translate_title():
    provider = CrossRef()
    q = title("transformer")
    query_terms, filters = provider._build_params(q)
    assert "transformer" in query_terms


def test_translate_author():
    provider = CrossRef()
    q = author("Vaswani")
    query_terms, filters = provider._build_params(q)
    assert "query.author=Vaswani" in filters


def test_translate_abstract():
    provider = CrossRef()
    q = abstract("attention mechanism")
    query_terms, filters = provider._build_params(q)
    assert "attention mechanism" in query_terms


def test_translate_keyword():
    provider = CrossRef()
    q = keyword("machine learning")
    query_terms, filters = provider._build_params(q)
    assert "machine learning" in query_terms


def test_translate_fulltext():
    provider = CrossRef()
    q = fulltext("neural network")
    query_terms, filters = provider._build_params(q)
    assert "neural network" in query_terms


def test_translate_doi():
    provider = CrossRef()
    q = doi("10.1234/example")
    query_terms, filters = provider._build_params(q)
    assert "filter=doi:10.1234/example" in filters


def test_translate_and():
    provider = CrossRef()
    q = title("BERT") & author("Google")
    query_terms, filters = provider._build_params(q)
    assert "BERT" in query_terms
    assert "query.author=Google" in filters


def test_translate_or():
    provider = CrossRef()
    q = title("BERT") | title("GPT")
    query_terms, filters = provider._build_params(q)
    assert "BERT" in query_terms
    assert "GPT" in query_terms


def test_translate_not():
    # CrossRef doesn't support NOT, so it should be ignored
    provider = CrossRef()
    q = ~title("survey")
    query_terms, filters = provider._build_params(q)
    assert "survey" not in query_terms
    assert len(filters) == 0


def test_translate_year_range():
    provider = CrossRef()
    q = year(2020, 2024)
    query_terms, filters = provider._build_params(q)
    assert "filter=from-pub-date:2020,until-pub-date:2024" in filters


def test_translate_year_start_only():
    provider = CrossRef()
    q = year(start=2020)
    query_terms, filters = provider._build_params(q)
    assert "filter=from-pub-date:2020" in filters


def test_translate_year_end_only():
    provider = CrossRef()
    q = year(end=2024)
    query_terms, filters = provider._build_params(q)
    assert "filter=until-pub-date:2024" in filters


def test_translate_complex_query():
    provider = CrossRef()
    q = (title("deep learning") & author("LeCun")) | keyword("CNN")
    query_terms, filters = provider._build_params(q)
    assert "deep learning" in query_terms
    assert "CNN" in query_terms
    assert "query.author=LeCun" in filters


def test_loads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("CROSSREF_API_KEY", "test-key-123")
    provider = CrossRef()
    assert provider._api_key == "test-key-123"


def test_explicit_api_key_overrides_env(monkeypatch):
    monkeypatch.setenv("CROSSREF_API_KEY", "env-key")
    provider = CrossRef(api_key="explicit-key")
    assert provider._api_key == "explicit-key"


def test_no_api_key_returns_none():
    original = os.environ.pop("CROSSREF_API_KEY", None)
    try:
        provider = CrossRef()
        assert provider._api_key is None
    finally:
        if original:
            os.environ["CROSSREF_API_KEY"] = original


def test_mailto_parameter():
    provider = CrossRef(mailto="test@example.com")
    assert provider._mailto == "test@example.com"


def test_provider_name():
    provider = CrossRef()
    assert provider.name == "crossref"


def test_base_url():
    provider = CrossRef()
    assert provider.BASE_URL == "https://api.crossref.org/works"


def test_parse_item_basic():
    provider = CrossRef()
    item = {
        "title": ["Test Paper Title"],
        "author": [
            {
                "given": "John",
                "family": "Doe",
                "ORCID": "https://orcid.org/0000-0001-2345-6789",
                "affiliation": [{"name": "Test University"}],
            }
        ],
        "DOI": "10.1234/test",
        "URL": "https://doi.org/10.1234/test",
        "published-print": {"date-parts": [[2023, 6, 15]]},
        "container-title": ["Test Journal"],
        "is-referenced-by-count": 42,
        "references-count": 25,
        "abstract": "<p>This is the abstract.</p>",
        "subject": ["Computer Science", "Machine Learning"],
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.title == "Test Paper Title"
    assert len(paper.authors) == 1
    assert paper.authors[0].name == "John Doe"
    assert paper.authors[0].orcid == "0000-0001-2345-6789"
    assert paper.authors[0].affiliation == "Test University"
    assert paper.doi == "10.1234/test"
    assert paper.url == "https://doi.org/10.1234/test"
    assert paper.year == 2023
    assert paper.publication_date is not None
    assert paper.publication_date.year == 2023
    assert paper.publication_date.month == 6
    assert paper.publication_date.day == 15
    assert paper.journal == "Test Journal"
    assert paper.citations_count == 42
    assert paper.references_count == 25
    assert paper.abstract == "This is the abstract."
    assert "Computer Science" in paper.topics
    assert paper.source == "crossref"
    assert paper.extras.get("crossref_doi") == "10.1234/test"


def test_parse_item_no_title():
    provider = CrossRef()
    item = {"author": [{"given": "John", "family": "Doe"}]}

    paper = provider._parse_item(item)
    assert paper is None


def test_parse_item_minimal():
    provider = CrossRef()
    item = {"title": ["Minimal Paper"]}

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.title == "Minimal Paper"
    assert paper.authors == ()
    assert paper.year == 0
    assert paper.doi is None


def test_parse_item_published_online_fallback():
    provider = CrossRef()
    item = {
        "title": ["Online Paper"],
        "published-online": {"date-parts": [[2024, 1, 1]]},
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.year == 2024


def test_parse_item_orcid_http_prefix():
    provider = CrossRef()
    item = {
        "title": ["ORCID Test"],
        "author": [
            {
                "given": "Jane",
                "family": "Smith",
                "ORCID": "http://orcid.org/0000-0002-1234-5678",
            }
        ],
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.authors[0].orcid == "0000-0002-1234-5678"


def test_parse_item_pdf_link():
    provider = CrossRef()
    item = {
        "title": ["PDF Paper"],
        "link": [
            {"content-type": "text/html", "URL": "https://example.com/paper"},
            {"content-type": "application/pdf", "URL": "https://example.com/paper.pdf"},
        ],
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.pdf_url == "https://example.com/paper.pdf"


def test_parse_item_open_access():
    provider = CrossRef()
    item = {
        "title": ["Open Access Paper"],
        "license": [
            {"content-version": "vor", "URL": "https://creativecommons.org/licenses/by/4.0/"}
        ],
    }

    paper = provider._parse_item(item)

    assert paper is not None
    assert paper.open_access is True
