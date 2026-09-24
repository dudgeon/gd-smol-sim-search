"""Fibonacci numbers with memoization."""

from functools import lru_cache


@lru_cache(maxsize=None)
def fibonacci(n: int) -> int:
    """Return the n-th Fibonacci number using a memoized recursive definition."""
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def fibonacci_sequence(count: int) -> list[int]:
    """Return the first `count` Fibonacci numbers."""
    return [fibonacci(i) for i in range(count)]
