# scimesh/search.py
import asyncio
import logging
import warnings
from collections import OrderedDict
from collections.abc import AsyncIterator, Coroutine
from typing import Any, Literal, overload

from scimesh.models import Paper, SearchResult
from scimesh.providers.base import Provider
from scimesh.query.combinators import Query
from scimesh.query.parser import parse

logger = logging.getLogger(__name__)

OnError = Literal["fail", "ignore", "warn"]

DEFAULT_DEDUPE_WINDOW = 10_000


async def take[T](n: int, aiter: AsyncIterator[T]) -> AsyncIterator[T]:
    """Take at most n items from an async iterator."""
    count = 0
    async for item in aiter:
        if count >= n:
            break
        yield item
        count += 1


async def chunked[T](
    stream: AsyncIterator[T],
    size: int,
    timeout: float = 1.0,
) -> AsyncIterator[list[T]]:
    """Group items from async stream into chunks.

    Args:
        stream: Source async iterator
        size: Max items per chunk
        timeout: Max seconds to wait before yielding partial chunk

    Yields:
        Lists of up to `size` items
    """
    buffer: list[T] = []
    aclose = getattr(stream, "aclose", None)

    async def get_next() -> T:
        """Wrapper to make __anext__ a proper coroutine for create_task."""
        return await stream.__anext__()

    try:
        while True:
            try:
                item = await asyncio.wait_for(get_next(), timeout=timeout)
                buffer.append(item)
                if len(buffer) >= size:
                    yield buffer
                    buffer = []
            except TimeoutError:
                # Yield partial buffer on timeout
                if buffer:
                    yield buffer
                    buffer = []
            except StopAsyncIteration:
                break

        # Yield remaining buffer after normal completion
        if buffer:
            yield buffer
    finally:
        # Close the source stream
        if aclose:
            try:
                await aclose()
            except Exception:
                pass


async def _search_stream(
    query: Query,
    providers: list[Provider],
    on_error: OnError,
    dedupe: bool = True,
    dedupe_window: int = DEFAULT_DEDUPE_WINDOW,
) -> AsyncIterator[Paper]:
    """Stream papers from multiple providers with optional windowed deduplication."""
    logger.info("Starting search with %s providers", len(providers))
    queue: asyncio.Queue[Paper | None | Exception] = asyncio.Queue()
    active_tasks = len(providers)
    seen: OrderedDict[str, None] = OrderedDict()

    async def fetch_one(provider: Provider) -> None:
        nonlocal active_tasks
        try:
            async with provider:
                async for paper in provider.search(query):
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

        if dedupe:
            key = item.doi or f"{item.title.lower()}:{item.year}"
            if key in seen:
                continue
            seen[key] = None
            if len(seen) > dedupe_window:
                seen.popitem(last=False)  # remove oldest

        yield item


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
        # Batch mode (default)
        result = await search(query, providers)

        # Streaming mode
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
