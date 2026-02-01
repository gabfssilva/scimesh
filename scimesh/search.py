import logging
import warnings
from collections.abc import AsyncIterator, Coroutine
from typing import Any, Literal, overload

import streamish as st

from scimesh.models import Paper, SearchResult
from scimesh.providers.base import Provider
from scimesh.query.combinators import Query
from scimesh.query.parser import parse

logger = logging.getLogger(__name__)

OnError = Literal["fail", "ignore", "warn"]

DEFAULT_DEDUPE_WINDOW = 10_000


async def _search_stream(
    query: Query,
    providers: list[Provider],
    on_error: OnError,
    dedupe: bool = True,
    dedupe_window: int = DEFAULT_DEDUPE_WINDOW,
) -> AsyncIterator[Paper]:
    """Stream papers from multiple providers with optional windowed deduplication."""
    logger.info("Starting search with %s providers", len(providers))

    async def safe_search(provider: Provider) -> AsyncIterator[Paper]:
        """Wrap provider search with error handling."""
        try:
            async with provider:
                async for paper in provider.search(query):
                    yield paper
        except Exception as e:
            if on_error == "fail":
                raise
            elif on_error == "warn":
                warnings.warn(f"Provider {provider.name} failed: {e}", stacklevel=3)

    def dedupe_key(paper: Paper) -> str:
        return paper.doi or f"{paper.title.lower()}:{paper.year}"

    streams = [safe_search(p) for p in providers]
    merged = st.merge(*streams)

    if dedupe:
        merged = st.distinct_by(dedupe_key, merged, window=dedupe_window)

    async for paper in merged:
        yield paper


async def _collect_results(stream: AsyncIterator[Paper]) -> SearchResult:
    """Collect streamed papers into a SearchResult."""
    papers: list[Paper] = []
    totals: dict[str, int] = {}

    async for paper in stream:
        papers.append(paper)
        totals[paper.source] = totals.get(paper.source, 0) + 1

    return SearchResult(papers=papers, total_by_provider=totals)


@overload
def search(
    query: Query | str,
    providers: list[Provider],
    on_error: OnError = ...,
    dedupe: bool = ...,
    stream: Literal[False] = ...,
) -> Coroutine[Any, Any, SearchResult]: ...


@overload
def search(
    query: Query | str,
    providers: list[Provider],
    on_error: OnError = ...,
    dedupe: bool = ...,
    *,
    stream: Literal[True],
) -> AsyncIterator[Paper]: ...


def search(
    query: Query | str,
    providers: list[Provider],
    on_error: OnError = "warn",
    dedupe: bool = True,
    stream: bool = False,
) -> Coroutine[Any, Any, SearchResult] | AsyncIterator[Paper]:
    """
    Search for papers across multiple providers.

    Args:
        query: Query AST or Scopus-style query string
        providers: List of providers to search
        on_error: Error handling mode - "fail", "ignore", or "warn"
        dedupe: Whether to deduplicate results (uses sliding window of 10k)
        stream: If True, yields papers as they arrive; if False, returns SearchResult

    Returns:
        If stream=False: Coroutine that resolves to SearchResult
        If stream=True: AsyncIterator yielding Paper objects

    Examples:

        result = await search(query, providers)


        async for paper in search(query, providers, stream=True):
            print(paper.title)
    """
    if isinstance(query, str):
        logger.debug("Parsing query string: %s", query)
        query = parse(query)

    paper_stream = _search_stream(query, providers, on_error, dedupe)
    if stream:
        return paper_stream
    return _collect_results(paper_stream)
