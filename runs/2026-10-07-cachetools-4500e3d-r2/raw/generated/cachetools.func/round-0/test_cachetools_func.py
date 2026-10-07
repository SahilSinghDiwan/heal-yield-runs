import builtins
import types

import pytest

# Import the module under test via its dotted path
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

    # "bob" is still cached
    assert greet("bob") == "hi bob"
    # No new call recorded for bob
    assert calls == ["alice", "bob", "carol", "alice"]


def test_unbounded_cache_grows_without_limit():
    """When maxsize is None the underlying cache dict should grow without eviction."""
    calls = []

    @func.lru_cache(maxsize=None)
    def square(x):
        calls.append(x)
        return x * x

    for i in range(5):
        assert square(i) == i * i
    # All calls were misses (first time)
    assert calls == list(range(5))

    # Re‑call the same values – all should be hits, no new calls recorded
    for i in range(5):
        assert square(i) == i * i
    assert calls == list(range(5))

    # Adding a new value should not evict any previous entry
    assert square(99) == 99 * 99
    assert calls == list(range(5)) + [99]

    # Verify cache_parameters reports maxsize=None
    assert square.cache_parameters() == {"maxsize": None, "typed": False}


def test_typed_cache_distinguishes_int_and_float():
    """When `typed=True` the cache key includes the argument types."""
    calls = []

    @func.lru_cache(maxsize=3, typed=True)
    def identity(x):
        calls.append(x)
        return x

    # 1 (int) and 1.0 (float) are distinct keys
    assert identity(1) == 1
    assert identity(1.0) == 1.0
    # Both calls should be recorded
    assert calls == [1, 1.0]

    # Re‑call with same types – should be hits
    assert identity(1) == 1
    assert identity(1.0) == 1.0
    assert calls == [1, 1.0]  # no new entries

    # Verify cache_parameters reports typed=True
    assert identity.cache_parameters() == {"maxsize": 3, "typed": True}


def test_lru_cache_eviction_order():
    """LRU cache should evict the least‑recently used entry when full."""
    calls = []

    @func.lru_cache(maxsize=2)
    def double(x):
        calls.append(x)
        return x * 2

    # Fill cache with two entries
    assert double(1) == 2
    assert double(2) == 4
    assert calls == [1, 2]

    # Access 1 to make it most‑recently used
    assert double(1) == 2
    assert calls == [1, 2]  # hit, no new call

    # Insert a new key, should evict 2 (least recently used)
    assert double(3) == 6
    assert calls == [1, 2, 3]

    # 2 was evicted, so a new call is required
    assert double(2) == 4
    assert calls == [1, 2, 3, 2]

    # Cache info reflects the state
    info = double.cache_info()
    # hits: one (the second call to 1), misses: four total calls minus hits
    assert info.hits == 1
    assert info.misses == 4
    assert info.maxsize == 2
    assert info.currsize == 2


def test_ttl_cache_respects_time_to_live():
    """TTL cache should expire entries after the given ttl."""
    # Use a mutable time source we can control
    current = [0.0]

    def timer():
        return current[0]

    calls = []

    @func.ttl_cache(maxsize=3, ttl=5, timer=timer)
    def inc(x):
        calls.append(x)
        return x + 1

    # First call – miss
    assert inc(10) == 11
    assert calls == [10]

    # Within ttl – hit
    current[0] += 4
    assert inc(10) == 11
    assert calls == [10]  # no new call

    # After ttl expires – miss again
    current[0] += 2  # total 6 > ttl
    assert inc(10) == 11
    assert calls == [10, 10]

    # Verify that other keys are independent
    assert inc(20) == 21
    assert calls == [10, 10, 20]

    # Check cache_parameters
    assert inc.cache_parameters() == {"maxsize": 3, "typed": False}


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

    # "y","2" should still be cached
    assert concat("y", "2") == "y2"
    assert calls == [("x", "1"), ("y", "2"), ("z", "3"), ("x", "1")]


def test_decorator_without_parentheses_uses_default_parameters():
    """When the decorator is applied directly to a function, default maxsize is used."""
    calls = []

    @func.lru_cache
    def add(a, b):
        calls.append((a, b))
        return a + b

    # Default maxsize is 128, so no eviction should happen for a few calls
    for i in range(5):
        assert add(i, i) == i + i
    assert calls == [(i, i) for i in range(5)]

    # Re‑call should hit the cache
    for i in range(5):
        assert add(i, i) == i + i
    assert calls == [(i, i) for i in range(5)]  # no new calls

    # Verify cache_parameters reflect the default maxsize
    assert add.cache_parameters() == {"maxsize": 128, "typed": False}
