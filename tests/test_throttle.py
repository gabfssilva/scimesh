# tests/test_throttle.py
import asyncio
import time

import pytest

from scimesh.throttle import throttle


@pytest.mark.asyncio
async def test_throttle_limits_concurrent_calls():
    """Test that throttle limits concurrent calls to the specified number."""
    max_concurrent = 0
    current_concurrent = 0

    @throttle(calls=2, period=0.1)
    async def track_concurrent():
        nonlocal max_concurrent, current_concurrent
        current_concurrent += 1
        max_concurrent = max(max_concurrent, current_concurrent)
        await asyncio.sleep(0.05)  # Simulate some work
        current_concurrent -= 1
        return current_concurrent

    # Run 5 calls concurrently
    await asyncio.gather(*[track_concurrent() for _ in range(5)])

    # Should never exceed 2 concurrent calls
    assert max_concurrent <= 2


@pytest.mark.asyncio
async def test_throttle_enforces_minimum_interval():
    """Test that throttle enforces minimum time between calls."""
    call_times: list[float] = []

    @throttle(calls=1, period=0.1)
    async def track_time():
        call_times.append(time.monotonic())
        return len(call_times)

    # Make 3 sequential calls
    for _ in range(3):
        await track_time()

    # Check intervals between calls
    for i in range(1, len(call_times)):
        interval = call_times[i] - call_times[i - 1]
        # Allow small tolerance for timing
        assert interval >= 0.09, f"Interval {interval} is less than required 0.1s"


@pytest.mark.asyncio
async def test_multiple_decorated_functions_have_independent_state():
    """Test that each decorated function has its own throttle state."""
    func1_calls: list[float] = []
    func2_calls: list[float] = []

    @throttle(calls=1, period=0.2)
    async def slow_func():
        func1_calls.append(time.monotonic())
        return "slow"

    @throttle(calls=1, period=0.01)
    async def fast_func():
        func2_calls.append(time.monotonic())
        return "fast"

    # Call both functions concurrently multiple times
    start = time.monotonic()

    # Run slow_func twice and fast_func twice concurrently
    results = await asyncio.gather(
        slow_func(),
        fast_func(),
        slow_func(),
        fast_func(),
    )

    time.monotonic() - start

    assert results == ["slow", "fast", "slow", "fast"]

    # slow_func should have intervals of ~0.2s, fast_func should have ~0.01s
    # The functions should operate independently
    if len(func1_calls) >= 2:
        slow_interval = func1_calls[1] - func1_calls[0]
        assert slow_interval >= 0.19, f"slow_func interval {slow_interval} too short"

    if len(func2_calls) >= 2:
        fast_interval = func2_calls[1] - func2_calls[0]
        assert fast_interval < 0.1, f"fast_func interval {fast_interval} should be short"


@pytest.mark.asyncio
async def test_throttle_preserves_function_metadata():
    """Test that throttle preserves function name and docstring."""

    @throttle(calls=1, period=1.0)
    async def my_function():
        """This is my docstring."""
        return 42

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "This is my docstring."


@pytest.mark.asyncio
async def test_throttle_passes_arguments_correctly():
    """Test that throttle correctly passes args and kwargs to the function."""

    @throttle(calls=1, period=0.01)
    async def add(a, b, *, c=0):
        return a + b + c

    result = await add(1, 2, c=3)
    assert result == 6


@pytest.mark.asyncio
async def test_throttle_propagates_exceptions():
    """Test that exceptions from the decorated function are propagated."""

    @throttle(calls=1, period=0.01)
    async def raise_error():
        raise ValueError("Test error")

    with pytest.raises(ValueError, match="Test error"):
        await raise_error()
