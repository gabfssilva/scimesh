from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scimesh.cache import PaperCache
from scimesh.download import OpenAccessDownloader, download_papers
from tests.integration.conftest import (
    ATTENTION_PAPER_DOI,
    BERT_PAPER_DOI,
    requires_unpaywall,
)


@requires_unpaywall
class TestOpenAccessDownload:
    @pytest.mark.asyncio
    async def test_download_known_paper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            results = []

            async for result in download_papers(
                [ATTENTION_PAPER_DOI],
                output_dir=output_dir,
                use_cache=False,
            ):
                results.append(result)

            assert len(results) == 1
            result = results[0]

            assert result.doi == ATTENTION_PAPER_DOI
            assert result.success, f"Download failed: {result.error}"
            assert result.filename is not None
            assert result.source == "open_access"

            pdf_path = output_dir / result.filename
            assert pdf_path.exists(), f"PDF not found at {pdf_path}"
            assert pdf_path.stat().st_size > 10_000, "PDF file is too small"

    @pytest.mark.asyncio
    async def test_download_returns_valid_pdf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            async for result in download_papers(
                [ATTENTION_PAPER_DOI],
                output_dir=output_dir,
                use_cache=False,
            ):
                if result.success:
                    pdf_path = output_dir / result.filename
                    content = pdf_path.read_bytes()
                    assert content[:4] == b"%PDF", "File does not start with PDF magic number"


@requires_unpaywall
class TestDownloadCaching:
    @pytest.mark.asyncio
    async def test_second_download_uses_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            cache_dir = Path(tmpdir) / "cache"
            cache = PaperCache(cache_dir)

            first_results = []
            async for result in download_papers(
                [ATTENTION_PAPER_DOI],
                output_dir=output_dir,
                cache=cache,
                use_cache=True,
            ):
                first_results.append(result)

            assert len(first_results) == 1
            assert first_results[0].success
            assert first_results[0].source == "open_access"

            second_results = []
            async for result in download_papers(
                [ATTENTION_PAPER_DOI],
                output_dir=output_dir,
                cache=cache,
                use_cache=True,
            ):
                second_results.append(result)

            assert len(second_results) == 1
            assert second_results[0].success
            assert second_results[0].source == "cache"

    @pytest.mark.asyncio
    async def test_cache_stores_pdf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            cache_dir = Path(tmpdir) / "cache"
            cache = PaperCache(cache_dir)

            async for _result in download_papers(
                [ATTENTION_PAPER_DOI],
                output_dir=output_dir,
                cache=cache,
                use_cache=True,
            ):
                pass

            cached_path = cache.get_pdf_path(ATTENTION_PAPER_DOI)
            assert cached_path is not None, "PDF should be cached"
            assert cached_path.exists()


@requires_unpaywall
class TestDownloadBatch:
    @pytest.mark.asyncio
    async def test_download_multiple_papers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            dois = [ATTENTION_PAPER_DOI, BERT_PAPER_DOI]

            results = []
            async for result in download_papers(
                dois,
                output_dir=output_dir,
                use_cache=False,
            ):
                results.append(result)

            assert len(results) == 2

            successful = [r for r in results if r.success]
            assert len(successful) >= 1, "At least one download should succeed"

            for result in successful:
                pdf_path = output_dir / result.filename
                assert pdf_path.exists()

    @pytest.mark.asyncio
    async def test_download_respects_concurrency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            dois = [ATTENTION_PAPER_DOI, BERT_PAPER_DOI]

            results = []
            async for result in download_papers(
                dois,
                output_dir=output_dir,
                use_cache=False,
                max_concurrency=1,
            ):
                results.append(result)

            assert len(results) == 2


class TestDownloadErrorHandling:
    @pytest.mark.asyncio
    async def test_invalid_doi_returns_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            results = []
            async for result in download_papers(
                ["10.invalid/nonexistent-doi-12345"],
                output_dir=output_dir,
                use_cache=False,
            ):
                results.append(result)

            assert len(results) == 1
            assert not results[0].success
            assert results[0].error is not None

    @pytest.mark.asyncio
    async def test_mixed_valid_invalid_dois(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            dois = [ATTENTION_PAPER_DOI, "10.invalid/fake"]

            results = []
            async for result in download_papers(
                dois,
                output_dir=output_dir,
                use_cache=False,
            ):
                results.append(result)

            assert len(results) == 2

            by_doi = {r.doi: r for r in results}
            assert by_doi["10.invalid/fake"].success is False


@requires_unpaywall
class TestDownloaderDirect:
    @pytest.mark.asyncio
    async def test_openaccess_downloader_directly(self):
        downloader = OpenAccessDownloader()

        async with downloader:
            pdf_bytes = await downloader.download(ATTENTION_PAPER_DOI)

        assert pdf_bytes is not None
        assert len(pdf_bytes) > 10_000
        assert pdf_bytes[:4] == b"%PDF"

    @pytest.mark.asyncio
    async def test_openaccess_downloader_invalid_doi(self):
        downloader = OpenAccessDownloader()

        async with downloader:
            pdf_bytes = await downloader.download("10.invalid/fake")

        assert pdf_bytes is None
