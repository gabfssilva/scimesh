"""Single entry point for searching providers and fetching papers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterable, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

import streamish as st

from scimesh.cache import (
    DEFAULT_FAILURE_TTL,
    DEFAULT_RESPONSE_TTL,
    Cache,
    key_to_doi,
    normalize_key,
)
from scimesh.download import Downloader, create_downloaders, start_downloaders
from scimesh.extract import extract_markdown, extractor_version
from scimesh.httpcache import CachingTransport
from scimesh.models import Paper, merge_papers
from scimesh.providers import create as create_provider
from scimesh.providers.base import Provider
from scimesh.query.combinators import Query
from scimesh.ratelimit import RateLimitedTransport
from scimesh.search import DEFAULT_DEDUPE_WINDOW, OnError, search

logger = logging.getLogger(__name__)

Direction = Literal["in", "out", "both"]


@dataclass(frozen=True, slots=True)
class Fetch:
    """Outcome of fetching a paper's PDF."""

    key: str
    path: Path | None = None
    source: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.path is not None


class Scimesh:
    """Search providers, fetch PDFs and text, cache everything once.

    Example:
        >>> async with Scimesh(["openalex", "arxiv"]) as sm:
        ...     async for paper in sm.search("TITLE(transformer)"):
        ...         print(paper.title)
        ...     text = await sm.text("10.1038/nature14539")
    """

    def __init__(
        self,
        providers: Sequence[str | Provider] = ("openalex",),
        cache: Cache | None = None,
        scihub: bool = False,
        host_concurrency: str | None = None,
        on_error: OnError = "warn",
        dedupe: bool = True,
        failure_ttl: timedelta = DEFAULT_FAILURE_TTL,
        response_ttl: timedelta = DEFAULT_RESPONSE_TTL,
        refresh: bool = False,
    ) -> None:
        self.providers = [create_provider(p) if isinstance(p, str) else p for p in providers]
        self.on_error: OnError = on_error
        self.dedupe = dedupe

        self._cache = cache
        self._owns_cache = cache is None
        self._scihub = scihub
        self._host_concurrency = host_concurrency
        self._failure_ttl = failure_ttl
        self._downloaders: list[Downloader] | None = None
        self._stack = AsyncExitStack()

        for provider in self.providers:
            provider.transport_factory = lambda: CachingTransport(
                self.cache,
                ttl=response_ttl,
                refresh=refresh,
                transport=RateLimitedTransport(),
            )

    @property
    def cache(self) -> Cache:
        """The paper cache, opened on first use."""
        if self._cache is None:
            self._cache = Cache()
        return self._cache

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._stack.aclose()
        self._downloaders = None
        if self._owns_cache and self._cache is not None:
            self._cache.close()
            self._cache = None

    def search(self, query: Query | str) -> AsyncIterator[Paper]:
        """Stream papers matching a query from every configured provider."""
        return search(
            query,
            providers=self.providers,
            on_error=self.on_error,
            dedupe=self.dedupe,
        )

    async def get(self, paper_id: str) -> Paper | None:
        """Fetch one paper by DOI or provider id, merging every provider that answers."""
        found: list[Paper] = []

        for provider in self.providers:
            if not provider.supports_get:
                continue
            try:
                async with provider:
                    paper = await provider.get(paper_id)
                if paper:
                    found.append(paper)
            except Exception as e:
                self._report(provider, e)

        if not found:
            return None
        return merge_papers(found)

    def citations(
        self,
        paper_id: str,
        direction: Direction = "both",
        max_results: int = 100,
    ) -> AsyncIterator[Paper]:
        """Stream papers citing (``in``) or cited by (``out``) a paper."""

        async def from_provider(provider: Provider) -> AsyncIterator[Paper]:
            if not provider.supports_citations:
                return
            try:
                async with provider:
                    async for paper in provider.citations(
                        paper_id, direction=direction, max_results=max_results
                    ):
                        yield paper
            except Exception as e:
                self._report(provider, e)

        merged = st.merge(*(from_provider(p) for p in self.providers))
        if self.dedupe:
            merged = st.distinct_by(_dedupe_key, merged, window=DEFAULT_DEDUPE_WINDOW)
        return st.take(max_results, merged)

    async def pdf(self, paper_id: str) -> Path | None:
        """Path to the paper's PDF, downloading it once if needed."""
        key = normalize_key(paper_id)

        cached = self.cache.pdf(key)
        if cached is not None:
            return cached

        if self.cache.failed_recently(key, self._failure_ttl):
            logger.debug("Skipping %s: download failed recently", key)
            return None

        doi = key_to_doi(key)
        if doi is None:
            self.cache.record_failure(key, "no DOI to download from")
            return None

        for downloader in await self._open_downloaders():
            try:
                content = await downloader.download(doi)
            except Exception as e:
                logger.debug("Downloader %s failed for %s: %s", downloader.name, key, e)
                continue
            if content:
                return self.cache.save_pdf(key, content, source=downloader.name)

        self.cache.record_failure(key, "no downloader found a PDF")
        return None

    async def text(self, paper_id: str) -> str | None:
        """Paper text as markdown, extracting from the PDF once if needed."""
        key = normalize_key(paper_id)

        cached = self.cache.text(key, extractor=extractor_version())
        if cached is not None:
            return cached

        path = await self.pdf(key)
        if path is None:
            return None

        text = await asyncio.to_thread(extract_markdown, path)
        self.cache.save_text(key, text, extractor_version())
        return text

    def fetch_many(
        self,
        paper_ids: Iterable[str],
        concurrency: int = 5,
        extract: bool = False,
    ) -> AsyncIterator[Fetch]:
        """Fetch PDFs for many papers, optionally extracting their text too."""

        async def fetch_one(paper_id: str) -> Fetch:
            key = normalize_key(paper_id)
            try:
                path = await self.pdf(key)
            except Exception as e:
                return Fetch(key=key, error=str(e))

            if path is None:
                return Fetch(key=key, error="not found")

            source = self.cache.source(key)
            if extract:
                try:
                    await self.text(key)
                except Exception as e:
                    return Fetch(key=key, path=path, source=source, error=f"extraction: {e}")

            return Fetch(key=key, path=path, source=source)

        return st.map_async(fetch_one, paper_ids, concurrency=concurrency)

    def search_text(self, term: str, limit: int = 100) -> list[str]:
        """Keys of cached papers whose text matches an FTS5 query."""
        return self.cache.search(term, limit=limit)

    async def _open_downloaders(self) -> list[Downloader]:
        if self._downloaders is None:
            self._downloaders = await start_downloaders(
                self._stack, create_downloaders(self._host_concurrency, self._scihub)
            )
        return self._downloaders

    def _report(self, provider: Provider, error: Exception) -> None:
        match self.on_error:
            case "fail":
                raise error
            case "warn":
                logger.warning("Provider %s failed: %s", provider.name, error)
            case "ignore":
                logger.debug("Provider %s failed: %s", provider.name, error)


def _dedupe_key(paper: Paper) -> str:
    return paper.doi or f"{paper.title.lower()}:{paper.year}"


__all__ = ["Direction", "Fetch", "Scimesh"]
