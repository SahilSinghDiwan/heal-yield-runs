import time
import types

import pytest

import cachetools.func as cachefunc


def test_basic_caching_decorator():
    """Basic LRU caching should record hits and misses correctly."""
    call_counter = {"count": 0}

    @cachefunc.lru_cache(maxsize=2)
    def add(a, b):
        call_counter["count"] += 1
        return a + b

    # First call: miss
    assert add(1, 2) == 3
    # Second call with same args: hit
    assert add(1, 2) == 3
    # Different args: miss
    assert add(2, 3) == 5

    info = add.cache_info()
    assert info.hits == 1
    assert info.misses == 2
    assert info.maxsize == 2
    assert info.currsize == 2
    # Underlying function should have been called exactly twice (once per miss)
    assert call_counter["count"] == 2


def test_maxsize_eviction_lru():
    """When the cache exceeds maxsize, the least recently used entry should be evicted."""
    call_counter = {"count": 0}

    @cachefunc.lru_cache(maxsize=2)
    def mul(x, y):
        call_counter["count"] += 1
        return x * y

    # Fill cache
    assert mul(1, 2) == 2  # miss
    assert mul(2, 3) == 6  # miss
    # Access first entry to make it most-recently used
    assert mul(1, 2) == 2  # hit
    # Add a new entry, causing eviction of the least-recently used (2,3)
    assert mul(3, 4) == 12  # miss

    info = mul.cache_info()
    # Hits: one (second call to (1,2)); Misses: three (first two fills + new entry)
    assert info.hits == 1
    assert info.misses == 3
    # Cache size should stay at maxsize
    assert info.currsize == 2
    # The evicted entry (2,3) should cause a recompute if called again
    assert mul(2, 3) == 6  # miss again
    info2 = mul.cache_info()
    assert info2.misses == 4
    assert info2.hits == 1


def test_typed_flag_separates_int_and_bool():
    """Typed flag should treat int and bool arguments as distinct keys."""
    call_counter = {"count": 0}

    @cachefunc.lru_cache(maxsize=4, typed=True)
    def identity(x):
        call_counter["count"] += 1
        return x

    # bool is a subclass of int, but with typed=True they are separate
    assert identity(True) is True   # miss
    assert identity(True) is True   # hit
    assert identity(1) == 1        # miss (different type)
    assert identity(1) == 1        # hit

    info = identity.cache_info()
    assert info.hits == 2
    assert info.misses == 2
    # Ensure both entries exist in cache
    assert info.currsize == 2
    # Underlying function called only on misses
    assert call_counter["count"] == 2


def test_fifo_eviction_order():
    """FIFO cache should evict the oldest inserted entry when full."""
    call_counter = {"count": 0}

    @cachefunc.fifo_cache(maxsize=3)
    def concat(a, b):
        call_counter["count"] += 1
        return f"{a}{b}"

    # Insert three distinct entries
    assert concat("a", "1") == "a1"  # miss
    assert concat("b", "2") == "b2"  # miss
    assert concat("c", "3") == "c3"  # miss

    # Cache is full; next insertion should evict the first entry ("a","1")
    assert concat("d", "4") == "d4"  # miss, eviction

    # The evicted entry should be recomputed
    assert concat("a", "1") == "a1"  # miss again

    info = concat.cache_info()
    # Total calls: 5 misses, 0 hits
    assert info.hits == 0
    assert info.misses == 5
    # Current size should stay at maxsize
    assert info.currsize == 3


def test_rr_cache_with_deterministic_choice():
    """RR cache with a deterministic choice function should replace a predictable entry."""
    # Deterministic choice: always pick the first key in the internal list
    def deterministic_choice(seq):
        return seq[0]

    call_counter = {"count": 0}

    @cachefunc.rr_cache(maxsize=2, choice=deterministic_choice)
    def square(x):
        call_counter["count"] += 1
        return x * x

    # Fill cache
    assert square(2) == 4  # miss
    assert square(3) == 9  # miss
    # Cache is full; next insertion will replace the first inserted key (2)
    assert square(4) == 16  # miss, replacement

    # The entry for 2 should have been evicted; calling again causes a miss
    assert square(2) == 4   # miss again

    info = square.cache_info()
    # Four distinct arguments, each causing a miss
    assert info.misses == 4
    # No hits because each call was a miss
    assert info.hits == 0
    # Cache size stays at maxsize
    assert info.currsize == 2


def test_ttl_cache_expiration():
    """TTL cache should expire entries after the given time-to-live."""
    # Use a controllable timer
    start = time.monotonic()
    timer = lambda: start + test_ttl_cache_expiration.elapsed

    test_ttl_cache_expiration.elapsed = 0.0
    call_counter = {"count": 0}

    @cachefunc.ttl_cache(maxsize=2, ttl=1.0, timer=timer)
    def inc(x):
        call_counter["count"] += 1
        return x + 1

    # First call: miss
    assert inc(10) == 11
    # Second call within TTL: hit
    assert inc(10) == 11
    # Advance time beyond TTL
    test_ttl_cache_expiration.elapsed = 1.5
    # Entry should be expired: miss again
    assert inc(10) == 11

    info = inc.cache_info()
    assert info.misses == 2
    assert info.hits == 1
    # After expiration, cache may have evicted the stale entry; size <= maxsize
    assert info.currsize <= 2
    # Underlying function called twice (first and after expiration)
    assert call_counter["count"] == 2


def test_none_maxsize_disables_caching():
    """When maxsize=None the decorator should behave as a cache without size limit."""
    call_counter = {"count": 0}

    @cachefunc.lru_cache(maxsize=None)
    def echo(x):
        call_counter["count"] += 1
        return x

    # Calls with same argument should result in a hit after the first call
    assert echo(1) == 1  # miss
    assert echo(1) == 1  # hit
    assert echo(2) == 2  # miss

    info = echo.cache_info()
    # Expect one hit (second call to 1) and two misses
    assert info.hits == 1
    assert info.misses == 2
    # No maxsize limit
    assert info.maxsize is None
    # Cache should contain both distinct keys
    assert info.currsize == 2
    # Underlying function called only on misses
    assert call_counter["count"] == 2
