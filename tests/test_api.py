"""Tests for the Scimesh facade."""

from collections.abc import AsyncIterator

import pytest

from scimesh.api import Scimesh
from scimesh.cache import Cache
from scimesh.download.base import Downloader
from scimesh.models import Author, Paper
from scimesh.providers.base import Provider
from scimesh.query.combinators import Query

PDF = b"%PDF-1.4 fake"


def paper(title="A Paper", doi=None, source="fake", **kwargs) -> Paper:
    return Paper(
        title=title,
        authors=(Author(name="Ada"),),
        year=2020,
        source=source,
        doi=doi,
        **kwargs,
    )


class FakeProvider(Provider):
    supports_get = True
    supports_citations = True

    def __init__(self, name="fake", papers=(), error=None):
        super().__init__()
        self.name = name
        self.papers = list(papers)
        self.error = error

    def _load_from_env(self) -> str | None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def search(self, query: Query) -> AsyncIterator[Paper]:
        if self.error:
            raise self.error
        for p in self.papers:
            yield p

    async def get(self, paper_id: str) -> Paper | None:
        if self.error:
            raise self.error
        return self.papers[0] if self.papers else None

    async def citations(self, paper_id, direction="both", max_results=100):
        for p in self.papers:
            yield p


class SearchOnlyProvider(FakeProvider):
    supports_get = False
    supports_citations = False


class FakeDownloader(Downloader):
    def __init__(self, name="fake", content: bytes | None = PDF, error=None):
        super().__init__()
        self.name = name
        self.content = content
        self.error = error
        self.calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def download(self, doi: str) -> bytes | None:
        self.calls.append(doi)
        if self.error:
            raise self.error
        return self.content


@pytest.fixture
def cache(tmp_path):
    with Cache(tmp_path / "scimesh") as cache:
        yield cache


def with_downloaders(monkeypatch, *downloaders):
    monkeypatch.setattr("scimesh.api.create_downloaders", lambda *_, **__: list(downloaders))


class TestSearch:
    async def test_streams_from_every_provider(self, cache):
        left = FakeProvider("left", [paper("Left", doi="10.1234/a")])
        right = FakeProvider("right", [paper("Right", doi="10.1234/b")])

        async with Scimesh([left, right], cache=cache) as sm:
            titles = {p.title async for p in sm.search("TITLE(x)")}

        assert titles == {"Left", "Right"}

    async def test_dedupes_by_doi(self, cache):
        left = FakeProvider("left", [paper("Same", doi="10.1234/a")])
        right = FakeProvider("right", [paper("Same", doi="10.1234/a")])

        async with Scimesh([left, right], cache=cache) as sm:
            found = [p async for p in sm.search("TITLE(x)")]

        assert len(found) == 1

    async def test_resolves_provider_names(self, cache):
        async with Scimesh(["arxiv", "openalex"], cache=cache) as sm:
            assert [p.name for p in sm.providers] == ["arxiv", "openalex"]

    async def test_rejects_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            Scimesh(["nope"])


class TestResponseCaching:
    async def test_providers_read_and_write_the_facade_cache(self, cache):
        from scimesh.httpcache import CachingTransport

        provider = FakeProvider("fake")

        async with Scimesh([provider], cache=cache):
            assert provider.transport_factory is not None
            transport = provider.transport_factory()

        assert isinstance(transport, CachingTransport)
        assert transport.cache is cache


class TestGet:
    async def test_merges_across_providers(self, cache):
        short = FakeProvider("short", [paper(doi="10.1234/a", abstract="short")])
        long = FakeProvider("long", [paper(doi="10.1234/a", abstract="a much longer abstract")])

        async with Scimesh([short, long], cache=cache) as sm:
            found = await sm.get("10.1234/a")

        assert found is not None
        assert found.abstract == "a much longer abstract"

    async def test_skips_providers_without_support(self, cache):
        unsupported = SearchOnlyProvider(
            "unsupported", [paper(doi="10.1234/a")], error=RuntimeError
        )
        supported = FakeProvider("supported", [paper("Found", doi="10.1234/a")])

        async with Scimesh([unsupported, supported], cache=cache) as sm:
            found = await sm.get("10.1234/a")

        assert found is not None
        assert found.title == "Found"

    async def test_none_when_nobody_answers(self, cache):
        async with Scimesh([FakeProvider("empty")], cache=cache) as sm:
            assert await sm.get("10.1234/a") is None

    async def test_warns_and_continues_on_error(self, cache):
        broken = FakeProvider("broken", error=RuntimeError("boom"))
        working = FakeProvider("working", [paper(doi="10.1234/a")])

        async with Scimesh([broken, working], cache=cache) as sm:
            assert await sm.get("10.1234/a") is not None

    async def test_raises_when_on_error_is_fail(self, cache):
        broken = FakeProvider("broken", error=RuntimeError("boom"))

        async with Scimesh([broken], cache=cache, on_error="fail") as sm:
            with pytest.raises(RuntimeError, match="boom"):
                await sm.get("10.1234/a")


class TestCitations:
    async def test_merges_and_dedupes(self, cache):
        left = FakeProvider("left", [paper("Citing", doi="10.1234/a")])
        right = FakeProvider(
            "right", [paper("Citing", doi="10.1234/a"), paper("Other", doi="10.1234/b")]
        )

        async with Scimesh([left, right], cache=cache) as sm:
            found = [p async for p in sm.citations("10.1234/seed")]

        assert sorted(p.title for p in found) == ["Citing", "Other"]

    async def test_respects_max_results(self, cache):
        papers = [paper(f"P{i}", doi=f"10.1234/{i}") for i in range(10)]

        async with Scimesh([FakeProvider("many", papers)], cache=cache) as sm:
            found = [p async for p in sm.citations("10.1234/seed", max_results=3)]

        assert len(found) == 3

    async def test_skips_providers_without_support(self, cache):
        async with Scimesh([SearchOnlyProvider("no", [paper()])], cache=cache) as sm:
            assert [p async for p in sm.citations("10.1234/seed")] == []


class TestPdf:
    async def test_downloads_and_caches(self, monkeypatch, cache):
        downloader = FakeDownloader()
        with_downloaders(monkeypatch, downloader)

        async with Scimesh([], cache=cache) as sm:
            path = await sm.pdf("10.1234/a")

        assert path is not None
        assert path.read_bytes() == PDF
        assert cache.source("10.1234/a") == "fake"

    async def test_second_call_is_served_from_cache(self, monkeypatch, cache):
        downloader = FakeDownloader()
        with_downloaders(monkeypatch, downloader)

        async with Scimesh([], cache=cache) as sm:
            await sm.pdf("10.1234/a")
            await sm.pdf("https://doi.org/10.1234/a")

        assert downloader.calls == ["10.1234/a"]

    async def test_falls_back_to_next_downloader(self, monkeypatch, cache):
        empty = FakeDownloader("empty", content=None)
        broken = FakeDownloader("broken", error=RuntimeError("boom"))
        working = FakeDownloader("working")
        with_downloaders(monkeypatch, empty, broken, working)

        async with Scimesh([], cache=cache) as sm:
            path = await sm.pdf("10.1234/a")

        assert path is not None
        assert cache.source("10.1234/a") == "working"

    async def test_records_failure_and_skips_retry(self, monkeypatch, cache):
        downloader = FakeDownloader(content=None)
        with_downloaders(monkeypatch, downloader)

        async with Scimesh([], cache=cache) as sm:
            assert await sm.pdf("10.1234/a") is None
            assert await sm.pdf("10.1234/a") is None

        assert downloader.calls == ["10.1234/a"]
        assert cache.failed_recently("10.1234/a") is True

    async def test_does_not_download_without_a_doi(self, monkeypatch, cache):
        downloader = FakeDownloader()
        with_downloaders(monkeypatch, downloader)

        async with Scimesh([], cache=cache) as sm:
            assert await sm.pdf("s2:abc") is None

        assert downloader.calls == []

    async def test_arxiv_id_downloads_by_doi(self, monkeypatch, cache):
        downloader = FakeDownloader()
        with_downloaders(monkeypatch, downloader)

        async with Scimesh([], cache=cache) as sm:
            assert await sm.pdf("1706.03762") is not None

        assert downloader.calls == ["10.48550/arxiv.1706.03762"]


class TestText:
    @pytest.fixture(autouse=True)
    def extractor(self, monkeypatch):
        calls: list[str] = []

        def extract(path):
            calls.append(str(path))
            return "# Extracted"

        monkeypatch.setattr("scimesh.api.extract_markdown", extract)
        monkeypatch.setattr("scimesh.api.extractor_version", lambda: "test/1")
        return calls

    async def test_extracts_once(self, monkeypatch, cache, extractor):
        with_downloaders(monkeypatch, FakeDownloader())

        async with Scimesh([], cache=cache) as sm:
            assert await sm.text("10.1234/a") == "# Extracted"
            assert await sm.text("10.1234/a") == "# Extracted"

        assert len(extractor) == 1
        assert cache.text("10.1234/a") == "# Extracted"

    async def test_reextracts_when_extractor_changes(self, monkeypatch, cache, extractor):
        with_downloaders(monkeypatch, FakeDownloader())
        cache.save_text("10.1234/a", "# Old", extractor="test/0")

        async with Scimesh([], cache=cache) as sm:
            assert await sm.text("10.1234/a") == "# Extracted"

        assert len(extractor) == 1

    async def test_none_without_pdf(self, monkeypatch, cache, extractor):
        with_downloaders(monkeypatch, FakeDownloader(content=None))

        async with Scimesh([], cache=cache) as sm:
            assert await sm.text("10.1234/a") is None

        assert extractor == []

    async def test_indexes_for_cache_search(self, monkeypatch, cache, extractor):
        with_downloaders(monkeypatch, FakeDownloader())

        async with Scimesh([], cache=cache) as sm:
            await sm.text("10.1234/a")
            assert sm.search_text("extracted") == ["10.1234/a"]


class TestFetchMany:
    async def test_reports_each_paper(self, monkeypatch, cache):
        with_downloaders(monkeypatch, FakeDownloader())

        async with Scimesh([], cache=cache) as sm:
            fetches = [f async for f in sm.fetch_many(["10.1234/a", "10.1234/b"])]

        assert {f.key for f in fetches} == {"10.1234/a", "10.1234/b"}
        assert all(f.success and f.source == "fake" for f in fetches)

    async def test_reports_failures(self, monkeypatch, cache):
        with_downloaders(monkeypatch, FakeDownloader(content=None))

        async with Scimesh([], cache=cache) as sm:
            fetches = [f async for f in sm.fetch_many(["10.1234/a"])]

        assert fetches[0].success is False
        assert fetches[0].error == "not found"

    async def test_extracts_when_asked(self, monkeypatch, cache):
        with_downloaders(monkeypatch, FakeDownloader())
        monkeypatch.setattr("scimesh.api.extract_markdown", lambda path: "# Extracted")
        monkeypatch.setattr("scimesh.api.extractor_version", lambda: "test/1")

        async with Scimesh([], cache=cache) as sm:
            fetches = [f async for f in sm.fetch_many(["10.1234/a"], extract=True)]

        assert fetches[0].success is True
        assert cache.text("10.1234/a") == "# Extracted"
