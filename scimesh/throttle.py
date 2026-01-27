# scimesh/throttle.py
"""Async throttle decorator for rate-limiting function calls."""

import asyncio
import time
from collections.abc import Callable
from functools import wraps
from types import CoroutineType
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def throttle(
    calls: int = 1, period: float = 1.0
) -> Callable[
    [Callable[P, CoroutineType[Any, Any, R]]],
    Callable[P, CoroutineType[Any, Any, R]],
]:
    """
    Decorator that limits async function calls.

    Uses an asyncio.Semaphore to limit concurrent calls and an asyncio.Lock
    with time.monotonic() to enforce minimum intervals between calls.

    Args:
        calls: Maximum number of concurrent calls allowed.
        period: Minimum time (in seconds) between consecutive calls.

    Example:
        @throttle(calls=1, period=2.0)  # max 1 call per 2s
        async def fetch(url): ...
    """

    def decorator(
        func: Callable[P, CoroutineType[Any, Any, R]],
    ) -> Callable[P, CoroutineType[Any, Any, R]]:
        # State is per-decorated-function (closure over these variables)
        semaphore = asyncio.Semaphore(calls)
        lock = asyncio.Lock()
        last_call_time: float = 0.0

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal last_call_time

            async with semaphore:
                # Enforce minimum interval between calls
                async with lock:
                    now = time.monotonic()
                    elapsed = now - last_call_time
                    if elapsed < period and last_call_time > 0:
                        await asyncio.sleep(period - elapsed)
                    last_call_time = time.monotonic()

                return await func(*args, **kwargs)

        return wrapper

    return decorator
