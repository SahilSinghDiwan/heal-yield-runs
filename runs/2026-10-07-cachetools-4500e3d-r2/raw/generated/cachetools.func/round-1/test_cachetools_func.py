import time
import math
import pytest
import cachetools.func as func


def test_fifo_cache_basic_eviction():
    """FIFO cache should keep at most `maxsize` entries and evict the oldest."""
    calls = []

    @func.fifo_cache(maxsize=2)
    def greet(name):
        calls.append(name)
        return f"hi {name}"

    # First two distinct calls are cached
    assert greet("alice") == "hi alice"
    assert greet("bob") == "hi bob"
    # No recomputation yet
    assert calls == ["alice", "bob"]

    # Third distinct call forces eviction of the first (alice)
    assert greet("carol") == "hi carol"
    # "carol" is new, so a new call is recorded
    assert calls == ["alice", "bob", "carol"]

    # "alice" was evicted, so calling again recomputes
    assert greet("alice") == "hi alice"
    assert calls == ["alice", "bob", "carol", "alice"]

    # "bob" is now the oldest and should have been evicted by the previous insertion
    # Therefore a new call is recorded
    assert greet("bob") == "hi bob"
    assert calls == ["alice", "bob", "carol", "alice", "bob"]


def test_unbounded_cache_grows_without_limit():
    """When maxsize=None the cache should grow without bound."""
    @func.lru_cache(maxsize=None)
    def square(x):
        return x * x

    # Call with a range of values
    for i in range(100):
        assert square(i) == i * i

    # The underlying cache should now contain 100 entries
    # The wrapper created by `cached` stores the cache in the attribute `cache`
    assert len(square.cache) == 100


def test_typed_cache_distinguishes_int_and_float():
    """Typed caches must treat 1 and 1.0 as distinct keys."""
    calls = []

    @func.lru_cache(maxsize=4, typed=True)
    def identity(x):
        calls.append(x)
        return x

    # Call with int and float versions
    assert identity(1) == 1
    assert identity(1.0) == 1.0
    # Both calls should have been recorded separately
    assert calls == [1, 1.0]

    # Re‑calling should hit the cache, not add new entries
    assert identity(1) == 1
    assert identity(1.0) == 1.0
    assert calls == [1, 1.0]


def test_lru_cache_eviction_order():
    """LRU cache evicts the least‑recently used entry when full."""
    calls = []

    @func.lru_cache(maxsize=2)
    def add(a, b):
        calls.append((a, b))
        return a + b

    # Fill the cache
    assert add(1, 2) == 3
    assert add(3, 4) == 7
    assert calls == [(1, 2), (3, 4)]

    # Access the first entry to make it most‑recently used
    assert add(1, 2) == 3
    # No new call recorded
    assert calls == [(1, 2), (3, 4)]

    # Adding a new entry should evict the least‑recently used (3,4)
    assert add(5, 6) == 11
    assert calls == [(1, 2), (3, 4), (5, 6)]

    # The evicted entry must be recomputed
    assert add(3, 4) == 7
    assert calls == [(1, 2), (3, 4), (5, 6), (3, 4)]


def test_ttl_cache_respects_time_to_live():
    """TTL cache should expire entries after the given TTL."""
    # Use a controllable timer
    start = time.monotonic()
    timer = lambda: start

    calls = []

    @func.ttl_cache(maxsize=2, ttl=0.1, timer=timer)
    def greet(name):
        calls.append(name)
        return f"hi {name}"

    # First call populates the cache
    assert greet("alice") == "hi alice"
    assert calls == ["alice"]

    # Within TTL, result is cached
    assert greet("alice") == "hi alice"
    assert calls == ["alice"]

    # Advance time beyond TTL
    nonlocal_start = {"value": start}
    def advance(dt):
        nonlocal_start["value"] += dt
        return nonlocal_start["value"]
    timer = lambda: advance(0.2)

    # The cached entry should be considered expired
    assert greet("alice") == "hi alice"
    assert calls == ["alice", "alice"]


def test_rr_cache_deterministic_eviction():
    """RR cache with a deterministic choice function should evict predictably."""
    # deterministic choice: always pick the first key in the internal list
    def first_choice(seq):
        return seq[0]

    calls = []

    @func.rr_cache(maxsize=2, choice=first_choice)
    def concat(a, b):
        calls.append((a, b))
        return f"{a}{b}"

    # Fill cache
    assert concat("x", "1") == "x1"
    assert concat("y", "2") == "y2"
    assert calls == [("x", "1"), ("y", "2")]

    # Adding a third entry should evict the first inserted ("x","1")
    assert concat("z", "3") == "z3"
    assert calls == [("x", "1"), ("y", "2"), ("z", "3")]

    # "x","1" was evicted, so a new call is needed
    assert concat("x", "1") == "x1"
    assert calls == [("x", "1"), ("y", "2"), ("z", "3"), ("x", "1")]

    # "y","2" should now be evicted by the previous insertion, so a new call occurs
    assert concat("y", "2") == "y2"
    assert calls == [("x", "1"), ("y", "2"), ("z", "3"), ("x", "1"), ("y", "2")]


def test_decorator_without_parentheses_uses_default_parameters():
    """Using a cache decorator without parentheses should apply default settings."""
    calls = []

    @func.lru_cache
    def double(x):
        calls.append(x)
        return x * 2

    # Default maxsize is 128; a few calls should be cached
    assert double(2) == 4
    assert double(3) == 6
    assert double(2) == 4
    # Only the first two distinct arguments should have caused calls
    assert calls == [2, 3]
