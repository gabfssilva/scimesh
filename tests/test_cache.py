"""Tests for the SQLite cache."""

from datetime import UTC, datetime, timedelta

import pytest

from scimesh.cache import Cache, default_root, key_to_doi, normalize_key, paper_key
from scimesh.models import Author, Paper

PDF = b"%PDF-1.4 fake"


@pytest.fixture
def cache(tmp_path):
    with Cache(tmp_path / "scimesh") as cache:
        yield cache


def paper(**kwargs) -> Paper:
    defaults = {
        "title": "A Paper",
        "authors": (Author(name="Ada"),),
        "year": 2020,
        "source": "arxiv",
    }
    return Paper(**{**defaults, **kwargs})


class TestNormalizeKey:
    @pytest.mark.parametrize(
        "identifier",
        [
            "10.1038/nature14539",
            "10.1038/Nature14539",
            "https://doi.org/10.1038/nature14539",
            "http://dx.doi.org/10.1038/nature14539",
            "doi:10.1038/nature14539",
            "  10.1038/nature14539  ",
        ],
    )
    def test_doi_forms_collapse(self, identifier):
        assert normalize_key(identifier) == "10.1038/nature14539"

    @pytest.mark.parametrize(
        "identifier",
        ["1706.03762", "arxiv:1706.03762", "ARXIV:1706.03762v2", "1706.03762v5"],
    )
    def test_arxiv_ids_collapse_onto_doi(self, identifier):
        assert normalize_key(identifier) == "10.48550/arxiv.1706.03762"

    def test_arxiv_doi_is_lowercased(self):
        assert normalize_key("10.48550/arXiv.1706.03762") == "10.48550/arxiv.1706.03762"

    def test_provider_id_keeps_prefix(self):
        assert normalize_key("s2:ABC123") == "s2:abc123"


class TestPaperKey:
    def test_prefers_doi(self):
        p = paper(doi="10.1038/Nature14539", extras={"arxiv_id": "1706.03762"})
        assert paper_key(p) == "10.1038/nature14539"

    def test_falls_back_to_arxiv_id(self):
        assert paper_key(paper(extras={"arxiv_id": "1706.03762"})) == "10.48550/arxiv.1706.03762"

    def test_falls_back_to_prefixed_provider_id(self):
        assert paper_key(paper(extras={"openalex_id": "W123"})) == "openalex:w123"
        assert paper_key(paper(extras={"semanticScholarId": "abc"})) == "s2:abc"

    def test_none_without_identifier(self):
        assert paper_key(paper()) is None


class TestKeyToDoi:
    def test_doi_key(self):
        assert key_to_doi("10.1038/nature14539") == "10.1038/nature14539"

    def test_provider_key(self):
        assert key_to_doi("s2:abc") is None


class TestRoot:
    def test_env_overrides_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SCIMESH_HOME", str(tmp_path / "elsewhere"))
        assert default_root() == tmp_path / "elsewhere"

    def test_defaults_to_home(self, monkeypatch):
        monkeypatch.delenv("SCIMESH_HOME", raising=False)
        assert default_root().name == ".scimesh"

    def test_wal_is_enabled(self, cache):
        mode = cache._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


class TestPdf:
    def test_missing_pdf(self, cache):
        assert cache.pdf("10.1234/absent") is None

    def test_roundtrip(self, cache):
        path = cache.save_pdf("10.1234/paper", PDF, source="open_access")

        assert path.read_bytes() == PDF
        assert cache.pdf("10.1234/paper") == path
        assert cache.source("10.1234/paper") == "open_access"

    def test_lookup_normalizes_key(self, cache):
        cache.save_pdf("10.1234/Paper", PDF, source="open_access")
        assert cache.pdf("https://doi.org/10.1234/paper") is not None

    def test_same_content_is_stored_once(self, cache):
        first = cache.save_pdf("10.1234/one", PDF, source="open_access")
        second = cache.save_pdf("10.1234/two", PDF, source="scihub")

        assert first == second
        assert len(list(cache.files_dir.glob("*.pdf"))) == 1

    def test_resave_replaces_content(self, cache):
        cache.save_pdf("10.1234/paper", PDF, source="open_access")
        cache.save_pdf("10.1234/paper", b"%PDF-1.7 other", source="scihub")

        assert cache.pdf("10.1234/paper").read_bytes() == b"%PDF-1.7 other"
        assert cache.source("10.1234/paper") == "scihub"

    def test_row_without_file_reads_as_missing(self, cache):
        path = cache.save_pdf("10.1234/paper", PDF, source="open_access")
        path.unlink()

        assert cache.pdf("10.1234/paper") is None

    def test_saving_clears_previous_failure(self, cache):
        cache.record_failure("10.1234/paper", "paywalled")
        cache.save_pdf("10.1234/paper", PDF, source="scihub")

        assert cache.failed_recently("10.1234/paper") is False


class TestText:
    def test_missing_text(self, cache):
        assert cache.text("10.1234/absent") is None

    def test_roundtrip(self, cache):
        cache.save_text("10.1234/paper", "# Title\n\nbody", extractor="v1")

        assert cache.text("10.1234/paper") == "# Title\n\nbody"
        assert cache.text("10.1234/paper", extractor="v1") == "# Title\n\nbody"

    def test_other_extractor_is_ignored(self, cache):
        cache.save_text("10.1234/paper", "body", extractor="v1")

        assert cache.text("10.1234/paper", extractor="v2") is None

    def test_resave_replaces(self, cache):
        cache.save_text("10.1234/paper", "old", extractor="v1")
        cache.save_text("10.1234/paper", "new", extractor="v2")

        assert cache.text("10.1234/paper") == "new"
        assert cache.text("10.1234/paper", extractor="v2") == "new"


class TestSearch:
    def test_finds_by_term(self, cache):
        cache.save_text("10.1234/a", "transformers attend to tokens", extractor="v1")
        cache.save_text("10.1234/b", "convolutions slide over pixels", extractor="v1")

        assert cache.search("transformers") == ["10.1234/a"]

    def test_stems_terms(self, cache):
        cache.save_text("10.1234/a", "the model attends to every token", extractor="v1")

        assert cache.search("attend") == ["10.1234/a"]

    def test_phrase_query(self, cache):
        cache.save_text("10.1234/a", "we study missing value imputation", extractor="v1")
        cache.save_text("10.1234/b", "imputation is missing from this text", extractor="v1")

        assert cache.search('"missing value"') == ["10.1234/a"]

    def test_respects_limit(self, cache):
        for i in range(5):
            cache.save_text(f"10.1234/{i}", "attention", extractor="v1")

        assert len(cache.search("attention", limit=2)) == 2

    def test_index_follows_updates(self, cache):
        cache.save_text("10.1234/a", "transformers", extractor="v1")
        cache.save_text("10.1234/a", "convolutions", extractor="v1")

        assert cache.search("transformers") == []
        assert cache.search("convolutions") == ["10.1234/a"]


class TestFailures:
    def test_unknown_key_never_failed(self, cache):
        assert cache.failed_recently("10.1234/paper") is False

    def test_recent_failure(self, cache):
        cache.record_failure("10.1234/paper", "paywalled")

        assert cache.failed_recently("10.1234/paper") is True

    def test_failure_expires(self, cache):
        cache.record_failure("10.1234/paper", "paywalled")

        assert cache.failed_recently("10.1234/paper", ttl=timedelta(0)) is False

    def test_stale_failure_is_replaced(self, cache):
        old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        cache._conn.execute(
            "INSERT INTO failures (key, error, failed_at) VALUES (?, ?, ?)",
            ("10.1234/paper", "paywalled", old),
        )

        assert cache.failed_recently("10.1234/paper") is False

        cache.record_failure("10.1234/paper", "paywalled again")

        assert cache.failed_recently("10.1234/paper") is True


class TestMaintenance:
    def test_stats(self, cache):
        cache.save_pdf("10.1234/a", PDF, source="open_access")
        cache.save_text("10.1234/a", "body", extractor="v1")
        cache.record_failure("10.1234/b", "paywalled")

        stats = cache.stats()

        assert (stats.documents, stats.texts, stats.failures) == (1, 1, 1)
        assert stats.bytes == len(PDF)

    def test_gc_drops_rows_whose_file_vanished(self, cache):
        path = cache.save_pdf("10.1234/a", PDF, source="open_access")
        path.unlink()

        report = cache.gc()

        assert report.dropped_rows == 1
        assert cache.stats().documents == 0

    def test_gc_deletes_unreferenced_files(self, cache):
        cache.save_pdf("10.1234/a", PDF, source="open_access")
        orphan = cache.files_dir / "deadbeef.pdf"
        orphan.write_bytes(b"orphan")
        leftover = cache.files_dir / "half-written.tmp"
        leftover.write_bytes(b"partial")

        report = cache.gc()

        assert report.deleted_files == 2
        assert not orphan.exists()
        assert not leftover.exists()
        assert cache.pdf("10.1234/a") is not None

    def test_clear(self, cache):
        cache.save_pdf("10.1234/a", PDF, source="open_access")
        cache.save_text("10.1234/a", "body", extractor="v1")
        cache.record_failure("10.1234/b", "paywalled")

        cache.clear()

        stats = cache.stats()
        assert (stats.documents, stats.texts, stats.failures) == (0, 0, 0)
        assert list(cache.files_dir.iterdir()) == []
        assert cache.search("body") == []


class TestResponses:
    def test_missing_response(self, cache):
        assert cache.response("https://api.example.com/works") is None

    def test_roundtrip(self, cache):
        cache.save_response("https://api.example.com/works", b'{"ok": true}', "application/json")

        body, content_type = cache.response("https://api.example.com/works")

        assert body == b'{"ok": true}'
        assert content_type == "application/json"

    def test_expires(self, cache):
        cache.save_response("https://api.example.com/works", b"{}", "application/json")

        assert cache.response("https://api.example.com/works", ttl=timedelta(0)) is None

    def test_resave_refreshes(self, cache):
        cache.save_response("https://api.example.com/works", b"old", "application/json")
        cache.save_response("https://api.example.com/works", b"new", "application/json")

        body, _ = cache.response("https://api.example.com/works")
        assert body == b"new"

    def test_urls_are_distinct_keys(self, cache):
        cache.save_response("https://api.example.com/works?page=1", b"one", None)
        cache.save_response("https://api.example.com/works?page=2", b"two", None)

        assert cache.response("https://api.example.com/works?page=1")[0] == b"one"
        assert cache.response("https://api.example.com/works?page=2")[0] == b"two"

    def test_expire_responses_drops_stale_only(self, cache):
        old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        cache.save_response("https://api.example.com/fresh", b"{}", None)
        cache._conn.execute(
            "INSERT INTO responses (url, body, content_type, fetched_at) VALUES (?, ?, ?, ?)",
            ("https://api.example.com/stale", b"{}", None, old),
        )

        assert cache.expire_responses() == 1
        assert cache.response("https://api.example.com/fresh") is not None

    def test_gc_expires_responses(self, cache):
        old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        cache._conn.execute(
            "INSERT INTO responses (url, body, content_type, fetched_at) VALUES (?, ?, ?, ?)",
            ("https://api.example.com/stale", b"{}", None, old),
        )

        assert cache.gc().expired_responses == 1

    def test_counted_in_stats_and_cleared(self, cache):
        cache.save_response("https://api.example.com/works", b"{}", None)

        assert cache.stats().responses == 1

        cache.clear()

        assert cache.stats().responses == 0
