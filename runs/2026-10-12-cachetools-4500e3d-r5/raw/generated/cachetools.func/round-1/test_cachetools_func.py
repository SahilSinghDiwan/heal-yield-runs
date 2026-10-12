import builtins
import types
import pytest
import itertools

# Import the module under test
from cachetools import func


def test_lru_cache_eviction_and_order():
    """LRU cache should evict the least‑recently used entry when full."""
    calls = {"count": 0}

    @func.lru_cache(maxsize=2)
    def f(x):
        calls["count"] += 1
        return x * 10

    # Fill the cache
    assert f(1) == 10  # miss
    assert f(2) == 20  # miss
    # Access 1 again – makes it most‑recently used
    assert f(1) == 10  # hit
    # Insert a new key, causing eviction of the least‑recently used (2)
    assert f(3) == 30  # miss, evicts 2

    # At this point, 2 should be recomputed (miss)
    calls_before = calls["count"]
    assert f(2) == 20  # miss
    assert calls["count"] == calls_before + 1

    # Verify cache parameters reflect the configuration
    params = f.cache_parameters()
    assert params["maxsize"] == 2
    assert params["typed"] is False


def test_typed_cache_separates_int_and_float():
    """When typed=True, int and float arguments are cached separately."""
    calls = {"count": 0}

    @func.lru_cache(maxsize=4, typed=True)
    def identity(x):
        calls["count"] += 1
        return x

    # First call with int 1 – miss
    assert identity(1) == 1
    # First call with float 1.0 – should be a separate miss
    assert identity(1.0) == 1.0
    # Re‑call with int 1 – hit
    calls_before = calls["count"]
    assert identity(1) == 1
    assert calls["count"] == calls_before  # no increment

    # Re‑call with float 1.0 – hit
    calls_before = calls["count"]
    assert identity(1.0) == 1.0
    assert calls["count"] == calls_before  # no increment

    params = identity.cache_parameters()
    assert params["typed"] is True
    assert params["maxsize"] == 4


def test_ttl_cache_with_custom_timer():
    """TTL cache should expire entries after the given ttl using a custom timer."""
    # Simple mutable timer
    timer = {"now": 0.0}

    def my_timer():
        return timer["now"]

    calls = {"count": 0}

    @func.ttl_cache(maxsize=2, ttl=5, timer=my_timer)
    def f(x):
        calls["count"] += 1
        return x + 100

    # First call – miss
    assert f(1) == 101
    assert calls["count"] == 1

    # Within ttl – hit
    timer["now"] += 3
    assert f(1) == 101
    assert calls["count"] == 1  # still a hit

    # After ttl expires – miss
    timer["now"] += 3  # total 6 > ttl
    assert f(1) == 101
    assert calls["count"] == 2  # recomputed

    params = f.cache_parameters()
    assert params["maxsize"] == 2
    assert params["typed"] is False


def test_rr_cache_deterministic_replacement():
    """RR cache with a deterministic choice function should evict predictable entries."""
    # Deterministic choice: always pick the first key in the internal list
    def first_choice(seq):
        return seq[0]

    calls = {"count": 0}

    @func.rr_cache(maxsize=2, choice=first_choice)
    def f(x):
        calls["count"] += 1
        return x * 2

    # Fill cache with two entries
    assert f(1) == 2  # miss
    assert f(2) == 4  # miss
    # Insert third entry – deterministic choice evicts the first inserted key (1)
    assert f(3) == 6  # miss, evicts key 1

    # Key 1 should be recomputed (miss)
    calls_before = calls["count"]
    assert f(1) == 2
    assert calls["count"] == calls_before + 1

    params = f.cache_parameters()
    assert params["maxsize"] == 2
    assert params["typed"] is False


def test_decorator_without_parentheses():
    """The cache decorators should work when used without parentheses."""
    calls = {"count": 0}

    @func.lru_cache
    def f(x):
        calls["count"] += 1
        return x * x

    # First call – miss
    assert f(3) == 9
    assert calls["count"] == 1
    # Second call – hit
    assert f(3) == 9
    assert calls["count"] == 1  # no increment

    params = f.cache_parameters()
    # Default maxsize for lru_cache is 128
    assert params["maxsize"] == 128
    assert params["typed"] is False


def test_cache_parameters_reflect_configuration():
    """All cache decorators should expose correct cache_parameters."""
    # LRU
    @func.lru_cache(maxsize=5, typed=True)
    def lru(x):
        return x

    # FIFO
    @func.fifo_cache(maxsize=3)
    def fifo(x):
        return x

    # LFU
    @func.lfu_cache(maxsize=None)  # unbounded
    def lfu(x):
        return x

    # TTL
    @func.ttl_cache(maxsize=7, ttl=10, typed=False)
    def ttl(x):
        return x

    # RR
    @func.rr_cache(maxsize=4, choice=lambda seq: seq[-1])
    def rr(x):
        return x

    assert lru.cache_parameters() == {"maxsize": 5, "typed": True}
    assert fifo.cache_parameters() == {"maxsize": 3, "typed": False}
    # Unbounded cache reports None for maxsize
    assert lfu.cache_parameters() == {"maxsize": None, "typed": False}
    assert ttl.cache_parameters() == {"maxsize": 7, "typed": False}
    assert rr.cache_parameters() == {"maxsize": 4, "typed": False}


def test_fifo_cache_eviction_order():
    """FIFO cache should evict the oldest entry when full."""
    calls = {"count": 0}

    @func.fifo_cache(maxsize=2)
    def f(x):
        calls["count"] += 1
        return x + 5

    # Insert two entries
    assert f(1) == 6  # miss
    assert f(2) == 7  # miss
    # Insert third entry – should evict the first (1)
    assert f(3) == 8  # miss, evicts key 1

    # Re‑call with 1 – miss again because it was evicted
    calls_before = calls["count"]
    assert f(1) == 6
    assert calls["count"] == calls_before + 1

    params = f.cache_parameters()
    assert params["maxsize"] == 2


def test_lfu_cache_frequency_preserves_frequent_items():
    """LFU cache should keep frequently accessed items longer."""
    calls = {"count": 0}

    @func.lfu_cache(maxsize=2)
    def f(x):
        calls["count"] += 1
        return x * 3

    # Access pattern: 1 (twice), 2 (once), then 3 (causes eviction)
    assert f(1) == 3  # miss
    assert f(2) == 6  # miss
    assert f(1) == 3  # hit, frequency of 1 becomes 2
    # Insert new key 3 – LFU should evict key 2 (frequency 1)
    assert f(3) == 9  # miss, evicts 2

    # Key 2 should be recomputed (miss)
    calls_before = calls["count"]
    assert f(2) == 6
    assert calls["count"] == calls_before + 1

    params = f.cache_parameters()
    assert params["maxsize"] == 2


def test_unbounded_cache_grows_without_limit():
    """When maxsize=None, the cache should grow without evicting entries."""
    calls = {"count": 0}

    @func.lru_cache(maxsize=None)
    def f(x):
        calls["count"] += 1
        return x * 7

    # Call with a series of distinct arguments
    for i in range(10):
        assert f(i) == i * 7

    # All calls were misses the first time
    assert calls["count"] == 10

    # Re‑call the same arguments – all should be hits (no additional calls)
    for i in range(10):
        before = calls["count"]
        assert f(i) == i * 7
        assert calls["count"] == before  # no increment

    params = f.cache_parameters()
    assert params["maxsize"] is None
