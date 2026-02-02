from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scimesh.download import download_papers
from scimesh.fulltext import FulltextIndex, extract_text_from_pdf
from tests.integration.conftest import (
    ATTENTION_PAPER_DOI,
    requires_unpaywall,
)


class TestFulltextIndexBasic:
    def test_add_and_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("paper1", "This paper discusses transformer architectures for NLP")
            index.add("paper2", "This paper is about convolutional neural networks for images")
            index.add("paper3", "Attention mechanisms in deep learning models")

            results = index.search("transformer")
            assert "paper1" in results
            assert "paper2" not in results

    def test_search_returns_relevant_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("paper1", "Attention is all you need for transformer sequence modeling")
            index.add("paper2", "BERT pre-training of deep bidirectional transformers")
            index.add("paper3", "Computer vision with convolutional networks")

            results = index.search("attention transformer")
            assert len(results) >= 1
            assert "paper1" in results

    def test_has_paper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("paper1", "Some content")

            assert index.has("paper1")
            assert not index.has("paper2")

    def test_remove_paper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("paper1", "Some content")
            assert index.has("paper1")

            removed = index.remove("paper1")
            assert removed
            assert not index.has("paper1")

    def test_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            assert index.count() == 0

            index.add("paper1", "Content 1")
            index.add("paper2", "Content 2")

            assert index.count() == 2

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("paper1", "Content 1")
            index.add("paper2", "Content 2")
            assert index.count() == 2

            index.clear()
            assert index.count() == 0

    def test_list_papers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("paper1", "Content 1")
            index.add("paper2", "Content 2")

            papers = index.list_papers()
            assert "paper1" in papers
            assert "paper2" in papers

    def test_update_existing_paper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("paper1", "Original content about cats")
            results1 = index.search("cats")
            assert "paper1" in results1

            index.add("paper1", "Updated content about dogs")
            results2 = index.search("cats")
            results3 = index.search("dogs")

            assert "paper1" not in results2
            assert "paper1" in results3


class TestFulltextSearchRanking:
    def test_more_relevant_ranked_higher(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("less_relevant", "This paper mentions attention once")
            index.add(
                "more_relevant",
                "Attention mechanisms attention models self-attention cross-attention",
            )

            results = index.search("attention")
            assert len(results) == 2
            assert results[0] == "more_relevant"


class TestFulltextFTS5Syntax:
    def test_phrase_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("paper1", "deep learning for natural language processing")
            index.add("paper2", "natural processing of deep language")

            results = index.search('"natural language"')
            assert "paper1" in results

    def test_or_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            index = FulltextIndex(db_path)

            index.add("paper1", "transformer models")
            index.add("paper2", "recurrent neural networks")
            index.add("paper3", "convolutional neural networks")

            results = index.search("transformer OR recurrent")
            assert "paper1" in results
            assert "paper2" in results
            assert "paper3" not in results


@requires_unpaywall
class TestFulltextWithRealPdf:
    @pytest.mark.asyncio
    async def test_index_downloaded_pdf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "pdfs"
            output_dir.mkdir()
            db_path = Path(tmpdir) / "test.db"

            results = []
            async for result in download_papers(
                [ATTENTION_PAPER_DOI],
                output_dir=output_dir,
                use_cache=False,
            ):
                results.append(result)

            if not results[0].success:
                pytest.skip("Could not download PDF")

            pdf_path = output_dir / results[0].filename
            text = extract_text_from_pdf(pdf_path)

            if text is None:
                pytest.skip("Could not extract text from PDF")

            index = FulltextIndex(db_path)
            index.add(ATTENTION_PAPER_DOI, text)

            search_results = index.search("attention transformer")
            assert ATTENTION_PAPER_DOI in search_results

    @pytest.mark.asyncio
    async def test_search_indexed_pdf_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "pdfs"
            output_dir.mkdir()
            db_path = Path(tmpdir) / "test.db"

            results = []
            async for result in download_papers(
                [ATTENTION_PAPER_DOI],
                output_dir=output_dir,
                use_cache=False,
            ):
                results.append(result)

            if not results[0].success:
                pytest.skip("Could not download PDF")

            pdf_path = output_dir / results[0].filename
            text = extract_text_from_pdf(pdf_path)

            if text is None:
                pytest.skip("Could not extract text from PDF")

            index = FulltextIndex(db_path)
            index.add(ATTENTION_PAPER_DOI, text)

            search_results = index.search('"self-attention"')
            assert ATTENTION_PAPER_DOI in search_results

            search_results = index.search("query key value")
            assert ATTENTION_PAPER_DOI in search_results


class TestExtractTextFromPdf:
    @pytest.mark.asyncio
    @requires_unpaywall
    async def test_extract_text_returns_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            results = []
            async for result in download_papers(
                [ATTENTION_PAPER_DOI],
                output_dir=output_dir,
                use_cache=False,
            ):
                results.append(result)

            if not results[0].success:
                pytest.skip("Could not download PDF")

            pdf_path = output_dir / results[0].filename
            text = extract_text_from_pdf(pdf_path)

            assert text is not None
            assert len(text) > 1000
            assert "attention" in text.lower()
