from __future__ import annotations

import pytest

from scimesh.api import Scimesh
from scimesh.cache import Cache
from scimesh.download import OpenAccessDownloader
from tests.integration.conftest import (
    ATTENTION_PAPER_DOI,
    BERT_PAPER_DOI,
    requires_unpaywall,
)


@pytest.fixture
def scimesh(tmp_path):
    return Scimesh([], cache=Cache(tmp_path / "scimesh"))


@requires_unpaywall
class TestOpenAccessDownload:
    async def test_download_known_paper(self, scimesh):
        async with scimesh as sm:
            path = await sm.pdf(ATTENTION_PAPER_DOI)

        assert path is not None, "Download failed"
        assert path.read_bytes()[:4] == b"%PDF"
        assert path.stat().st_size > 10_000, "PDF file is too small"

    async def test_source_is_recorded(self, scimesh):
        async with scimesh as sm:
            await sm.pdf(ATTENTION_PAPER_DOI)

        assert sm.cache.source(ATTENTION_PAPER_DOI) == "open_access"


@requires_unpaywall
class TestDownloadCaching:
    async def test_second_download_is_served_from_cache(self, scimesh):
        async with scimesh as sm:
            first = await sm.pdf(ATTENTION_PAPER_DOI)
            second = await sm.pdf(ATTENTION_PAPER_DOI)

        assert first == second

    async def test_text_is_extracted_once(self, scimesh):
        async with scimesh as sm:
            text = await sm.text(ATTENTION_PAPER_DOI)

            assert text is not None
            assert "attention" in text.lower()
            assert sm.cache.text(ATTENTION_PAPER_DOI) == text
            assert sm.search_text("attention") == [ATTENTION_PAPER_DOI.lower()]


@requires_unpaywall
class TestFetchMany:
    async def test_fetches_several_papers(self, scimesh):
        async with scimesh as sm:
            fetches = [f async for f in sm.fetch_many([ATTENTION_PAPER_DOI, BERT_PAPER_DOI])]

        assert len(fetches) == 2
        assert any(f.success for f in fetches), "At least one download should succeed"

    async def test_reports_failure_for_invalid_doi(self, scimesh):
        async with scimesh as sm:
            fetches = [f async for f in sm.fetch_many(["10.invalid/fake"])]

        assert fetches[0].success is False
        assert fetches[0].error is not None


class TestDownloadErrorHandling:
    async def test_invalid_doi_is_remembered_as_a_failure(self, scimesh):
        async with scimesh as sm:
            assert await sm.pdf("10.9999/nonexistent-doi-12345") is None

        assert sm.cache.failed_recently("10.9999/nonexistent-doi-12345") is True


@requires_unpaywall
class TestDownloaderDirect:
    async def test_openaccess_downloader_directly(self):
        async with OpenAccessDownloader() as downloader:
            pdf_bytes = await downloader.download(ATTENTION_PAPER_DOI)

        assert pdf_bytes is not None
        assert len(pdf_bytes) > 10_000
        assert pdf_bytes[:4] == b"%PDF"

    async def test_openaccess_downloader_invalid_doi(self):
        async with OpenAccessDownloader() as downloader:
            pdf_bytes = await downloader.download("10.invalid/fake")

        assert pdf_bytes is None
