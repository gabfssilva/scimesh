# scimesh/search.py
import asyncio
import logging
import warnings
from collections.abc import AsyncIterator, Coroutine
from typing import Any, Literal, overload

from scimesh.models import Paper, SearchResult
from scimesh.providers.base import Provider
from scimesh.query.combinators import Query
from scimesh.query.parser import parse

logger = logging.getLogger(__name__)

OnError = Literal["fail", "ignore", "warn"]


async def take[T](n: int, aiter: AsyncIterator[T]) -> AsyncIterator[T]:
    """Take at most n items from an async iterator."""
    count = 0
    async for item in aiter:
        if count >= n:
            break
        yield item
        count += 1


async def _search_stream(
    query: Query,
    providers: list[Provider],
    max_results: int,
    on_error: OnError,
) -> AsyncIterator[Paper]:
    """Internal streaming implementation."""
    logger.info("Starting streaming search with %s providers", len(providers))
    queue: asyncio.Queue[Paper | None | Exception] = asyncio.Queue()
    active_tasks = len(providers)

    async def fetch_one(provider: Provider) -> None:
        nonlocal active_tasks
        try:
            async with provider:
                async for paper in provider.search(query, max_results):
                    await queue.put(paper)
        except Exception as e:
            if on_error == "fail":
                await queue.put(e)
            elif on_error == "warn":
                warnings.warn(f"Provider {provider.name} failed: {e}", stacklevel=2)
        finally:
            active_tasks -= 1
            if active_tasks == 0:
                await queue.put(None)  # Signal completion

    # Start all provider tasks
    for provider in providers:
        asyncio.create_task(fetch_one(provider))

    # Yield papers as they arrive
    while True:
        item = await queue.get()
        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        yield item


async def _search_batch(
    query: Query,
    providers: list[Provider],
    max_results: int,
    on_error: OnError,
    dedupe: bool,
) -> SearchResult:
    """Internal batch implementation."""
    logger.info("Starting batch search with %s providers", len(providers))

    async def fetch_one(
        provider: Provider,
    ) -> tuple[str, list[Paper], Exception | None]:
        try:
            async with provider:
                papers = [p async for p in provider.search(query, max_results)]
                return (provider.name, papers, None)
        except Exception as e:
            return (provider.name, [], e)

    results = await asyncio.gather(*[fetch_one(p) for p in providers])

    all_papers: list[Paper] = []
    errors: dict[str, Exception] = {}
    totals: dict[str, int] = {}

    for name, papers, error in results:
        if error:
            if on_error == "fail":
                raise error
            elif on_error == "warn":
                warnings.warn(f"Provider {name} failed: {error}", stacklevel=2)
            errors[name] = error
        else:
            all_papers.extend(papers)
            totals[name] = len(papers)

    result = SearchResult(papers=all_papers, errors=errors, total_by_provider=totals)
    logger.info("Search complete: %s papers from %s providers", len(all_papers), len(totals))
    return result.dedupe() if dedupe else result


@overload
def search(
    query: Query | str,
    providers: list[Provider],
    max_results: int = ...,
    on_error: OnError = ...,
    dedupe: bool = ...,
    stream: Literal[False] = ...,
) -> Coroutine[Any, Any, SearchResult]: ...


@overload
def search(
    query: Query | str,
    providers: list[Provider],
    max_results: int = ...,
    on_error: OnError = ...,
    dedupe: bool = ...,
    *,
    stream: Literal[True],
) -> AsyncIterator[Paper]: ...


def search(
    query: Query | str,
    providers: list[Provider],
    max_results: int = 100,
    on_error: OnError = "warn",
    dedupe: bool = True,
    stream: bool = False,
) -> Coroutine[Any, Any, SearchResult] | AsyncIterator[Paper]:
    """
    Search for papers across multiple providers.

    Args:
        query: Query AST or Scopus-style query string
        providers: List of providers to search
        max_results: Maximum results per provider
        on_error: Error handling mode - "fail", "ignore", or "warn"
        dedupe: Whether to deduplicate results by DOI (ignored when stream=True)
        stream: If True, yields papers as they arrive; if False, returns SearchResult

    Returns:
        If stream=False: Coroutine that resolves to SearchResult
        If stream=True: AsyncIterator yielding Paper objects

    Examples:
        # Batch mode (default)
        result = await search(query, providers)

        # Streaming mode
        async for paper in search(query, providers, stream=True):
            print(paper.title)
    """
    if isinstance(query, str):
        logger.debug("Parsing query string: %s", query)
        query = parse(query)

    if stream:
        return _search_stream(query, providers, max_results, on_error)
    else:
        return _search_batch(query, providers, max_results, on_error, dedupe)
