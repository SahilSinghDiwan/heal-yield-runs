import time
import types
import pytest
from cachetools import func as cachefunc


def make_counter_func():
    """Return a function that returns the current call count and a mutable counter."""
    counter = {"calls": 0}

    def f(x):
        counter["calls"] += 1
        return (x, counter["calls"])

    return f, counter


@pytest.mark.parametrize(
    "decorator_name",
    ["fifo_cache", "lfu_cache", "lru_cache", "rr_cache", "ttl_cache"],
)
def test_basic_caching_decorator(decorator_name):
    """Calling the same arguments twice should hit the cache (except ttl with expiry)."""
    decorator = getattr(cachefunc, decorator_name)

    # Use a small maxsize to keep things simple; ttl will ignore maxsize for this test
    if decorator_name == "ttl_cache":
        # ttl of 10 seconds, timer is real monotonic
        cached = decorator(maxsize=2, ttl=10)(lambda x: x * 2)
    else:
        cached = decorator(maxsize=2)(lambda x: x * 2)

    # first call – cache miss
    assert cached(3) == 6
    # second call with same argument – cache hit (no recomputation)
    assert cached(3) == 6

    # The wrapper provides cache_info() because info=True was set
    info = cached.cache_info()
    assert info.hits == 1
    assert info.misses == 1
    assert info.maxsize == 2
    assert info.currsize == 1


def test_maxsize_eviction_lru():
    """LRU cache should evict the least‑recently used entry when maxsize is exceeded."""
    @cachefunc.lru_cache(maxsize=2)
    def square(x):
        return x * x

    # Fill cache with two entries
    assert square(2) == 4  # miss
    assert square(3) == 9  # miss

    # Access one of them to make it most‑recently used
    assert square(2) == 4  # hit

    # Insert a third distinct key, causing eviction of the LRU (which is 3)
    assert square(4) == 16  # miss

    info = square.cache_info()
    # After eviction we should have 2 hits (the second call to 2) and 3 misses total
    assert info.hits == 1
    assert info.misses == 3
    assert info.currsize == 2

    # 3 should have been evicted, so recompute
    assert square(3) == 9  # miss again
    info = square.cache_info()
    assert info.misses == 4
    assert info.currsize == 2


def test_typed_flag_separates_int_and_bool():
    """When typed=True, int 1 and bool True are cached separately."""
    @cachefunc.lru_cache(maxsize=2, typed=True)
    def identity(x):
        return x

    # First call with int 1 – miss
    assert identity(1) == 1
    # Call with bool True – should be a separate cache entry (miss)
    assert identity(True) is True
    # Second call with int 1 – hit
    assert identity(1) == 1

    info = identity.cache_info()
    assert info.hits == 1
    assert info.misses == 2
    assert info.currsize == 2


def test_fifo_eviction_order():
    """FIFO cache evicts entries in insertion order."""
    @cachefunc.fifo_cache(maxsize=2)
    def inc(x):
        return x + 1

    # Insert three distinct keys
    assert inc(1) == 2  # miss
    assert inc(2) == 3  # miss
    assert inc(3) == 4  # miss, should evict key 1

    # Key 1 should be recomputed (miss)
    assert inc(1) == 2
    info = inc.cache_info()
    assert info.misses == 4
    assert info.currsize == 2


def test_rr_cache_with_deterministic_choice():
    """RR cache with a deterministic choice function behaves predictably."""
    # deterministic choice: always pick the first element
    deterministic_choice = lambda seq: seq[0]

    @cachefunc.rr_cache(maxsize=2, choice=deterministic_choice)
    def double(x):
        return x * 2

    # Fill cache
    assert double(10) == 20  # miss
    assert double(20) == 40  # miss

    # Insert third key, causing eviction of the first key (10) because choice picks first
    assert double(30) == 60  # miss

    # 10 should be recomputed
    assert double(10) == 20  # miss again
    info = double.cache_info()
    assert info.misses == 4
    assert info.currsize == 2


def test_ttl_cache_expiration():
    """TTL cache should expire entries after the given ttl."""
    # Use a controllable timer
    current = {"t": 0.0}

    def fake_timer():
        return current["t"]

    @cachefunc.ttl_cache(maxsize=2, ttl=5, timer=fake_timer)
    def add_one(x):
        return x + 1

    # First call – miss, stores at time 0
    assert add_one(5) == 6
    info = add_one.cache_info()
    assert info.hits == 0
    assert info.misses == 1
    assert info.currsize == 1

    # Second call with same arg before ttl – hit
    assert add_one(5) == 6
    info = add_one.cache_info()
    assert info.hits == 1
    assert info.misses == 1

    # Advance time beyond ttl
    current["t"] += 6.0

    # Cache entry should be expired – miss again
    assert add_one(5) == 6
    info = add_one.cache_info()
    assert info.hits == 1
    assert info.misses == 2
    assert info.currsize == 1  # still one entry after recompute


def test_none_maxsize_disables_caching():
    """When maxsize=None the decorator should behave as a no‑op cache."""
    @cachefunc.lru_cache(maxsize=None)
    def echo(x):
        return x

    # Each call should be a miss (no caching)
    assert echo(1) == 1
    assert echo(1) == 1
    assert echo(2) == 2

    info = echo.cache_info()
    # All calls are misses; hits should be zero
    assert info.hits == 0
    assert info.misses == 3
    # maxsize is None, currsize should stay 0
    assert info.maxsize is None
    assert info.currsize == 0
