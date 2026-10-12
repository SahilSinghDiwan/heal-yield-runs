import time

import pytest
from cachetools import func


def test_fifo_cache_eviction():
    @func.fifo_cache(maxsize=2)
    def square(x):
        return x * x

    # Fill cache
    assert square(2) == 4
    assert square(3) == 9
    # Cache is full; next entry evicts the first (2)
    assert square(4) == 16
    info = square.cache_info()
    assert info.currsize == 2

    # 2 should be a miss now
    hits_before = info.hits
    misses_before = info.misses
    assert square(2) == 4
    info2 = square.cache_info()
    assert info2.misses >= misses_before + 1
    assert info2.hits >= hits_before


def test_lru_cache_eviction():
    @func.lru_cache(maxsize=2)
    def inc(x):
        return x + 1

    # Fill cache
    assert inc(1) == 2
    assert inc(2) == 3
    # Access 1 again to make it most-recently used
    assert inc(1) == 2
    # Adding a new entry evicts the least-recently used (2)
    assert inc(3) == 4
    info = inc.cache_info()
    assert info.currsize == 2

    # 2 should be a miss now
    hits_before = info.hits
    misses_before = info.misses
    assert inc(2) == 3
    info2 = inc.cache_info()
    assert info2.misses >= misses_before + 1
    assert info2.hits >= hits_before


def test_lfu_cache_eviction():
    @func.lfu_cache(maxsize=2)
    def double(x):
        return x * 2

    # Fill cache
    assert double(1) == 2
    assert double(2) == 4
    # Increase frequency of key 1
    assert double(1) == 2
    # Adding a new entry should evict the least-frequently used (2)
    assert double(3) == 6
    info = double.cache_info()
    assert info.currsize == 2

    # 2 should be a miss now
    hits_before = info.hits
    misses_before = info.misses
    assert double(2) == 4
    info2 = double.cache_info()
    assert info2.misses >= misses_before + 1
    assert info2.hits >= hits_before


def test_rr_cache_deterministic_eviction():
    # Deterministic choice function that always selects the first key
    def first_choice(seq):
        return seq[0]

    @func.rr_cache(maxsize=2, choice=first_choice)
    def identity(x):
        return x

    # Populate cache
    assert identity(1) == 1
    assert identity(2) == 2
    # Adding a third entry evicts the first key (1) due to our choice function
    assert identity(3) == 3
    info = identity.cache_info()
    assert info.currsize == 2

    # 1 should be a miss now
    hits_before = info.hits
    misses_before = info.misses
    assert identity(1) == 1
    info2 = identity.cache_info()
    assert info2.misses >= misses_before + 1
    # Since this call was a miss, hits should not increase
    assert info2.hits == hits_before


def test_ttl_cache_expiration():
    @func.ttl_cache(maxsize=2, ttl=0.1, timer=time.monotonic)
    def add(x, y):
        return x + y

    # First call stores result
    assert add(1, 2) == 3
    info = add.cache_info()
    assert info.currsize == 1

    # Wait for the entry to expire
    time.sleep(0.15)

    # Next call recomputes the value
    assert add(1, 2) == 3
    info2 = add.cache_info()
    assert info2.misses >= info.misses + 1


def test_typed_cache_distinguishes_types():
    @func.lru_cache(maxsize=2, typed=True)
    def concat(a, b):
        return str(a) + str(b)

    # First call with ints
    assert concat(1, 2) == "12"
    # Same numeric values but different types should be a miss
    assert concat(1.0, 2.0) == "12.0"
    info = concat.cache_info()
    assert info.currsize == 2

    # Repeating the int call should be a hit
    hits_before = info.hits
    assert concat(1, 2) == "12"
    info2 = concat.cache_info()
    assert info2.hits >= hits_before + 1


def test_decorator_without_parentheses():
    @func.lru_cache
    def const():
        return 42

    # First call stores the result
    assert const() == 42
    info = const.cache_info()
    assert info.currsize == 1

    # Second call should be a hit
    hits_before = info.hits
    assert const() == 42
    info2 = const.cache_info()
    assert info2.hits >= hits_before + 1


def test_unbounded_cache_behaviour():
    @func.lru_cache(maxsize=None)
    def identity(x):
        return x

    # Populate with many entries; none should be evicted
    for i in range(100):
        assert identity(i) == i

    info = identity.cache_info()
    assert info.maxsize is None
    assert info.currsize == 100
