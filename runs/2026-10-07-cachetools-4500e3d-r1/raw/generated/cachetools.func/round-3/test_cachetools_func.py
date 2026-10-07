import pytest
import types

import cachetools.func as cachefunc
from cachetools import keys


def test_cache_parameters_reflect_arguments():
    @cachefunc.lru_cache(maxsize=10, typed=True)
    def add(a, b):
        return a + b

    params = add.cache_parameters()
    assert isinstance(params, dict)
    assert params["maxsize"] == 10
    assert params["typed"] is True


def test_typed_flag_affects_key():
    @cachefunc.lru_cache(maxsize=2, typed=True)
    def identity(x):
        return x

    # First call caches integer 1
    assert identity(1) == 1
    # Call with float 1.0 should be treated as a different key because typed=True
    assert identity(1.0) == 1.0
    # Cache should now contain two entries
    cache_dict = identity.cache  # type: ignore[attr-defined]
    assert len(cache_dict) == 2
    # Ensure both values are present
    values = set(cache_dict.values())
    assert values == {1, 1.0}


def test_fifo_cache_eviction():
    @cachefunc.fifo_cache(maxsize=2)
    def square(x):
        return x * x

    # Fill cache with two entries
    assert square(1) == 1
    assert square(2) == 4
    cache_dict = square.cache  # type: ignore[attr-defined]
    assert len(cache_dict) == 2

    # Adding a third entry should evict the first (key for 1)
    assert square(3) == 9
    assert len(square.cache) == 2
    # The value for 1 should no longer be cached
    key1 = keys.hashkey(square, (1,), {})
    assert key1 not in square.cache


def test_lru_cache_eviction():
    @cachefunc.lru_cache(maxsize=2)
    def cube(x):
        return x * x * x

    # Populate cache
    assert cube(1) == 1
    assert cube(2) == 8
    # Access 1 to make it most-recently used
    assert cube(1) == 1
    # Insert a new value, should evict 2 (least recently used)
    assert cube(3) == 27
    cache_dict = cube.cache  # type: ignore[attr-defined]
    assert len(cache_dict) == 2
    key2 = keys.hashkey(cube, (2,), {})
    assert key2 not in cache_dict
    # Ensure 1 is still cached
    key1 = keys.hashkey(cube, (1,), {})
    assert key1 in cache_dict


def test_rr_cache_deterministic_eviction():
    # deterministic choice: always pick the first element
    def first_choice(seq):
        return seq[0]

    @cachefunc.rr_cache(maxsize=2, choice=first_choice)
    def inc(x):
        return x + 1

    # Fill cache
    assert inc(1) == 2
    assert inc(2) == 3
    # Adding third entry should evict the first inserted (key for 1)
    assert inc(3) == 4
    cache_dict = inc.cache  # type: ignore[attr-defined]
    assert len(cache_dict) == 2
    key1 = keys.hashkey(inc, (1,), {})
    assert key1 not in cache_dict
    # Ensure 2 is still cached
    key2 = keys.hashkey(inc, (2,), {})
    assert key2 in cache_dict


def test_ttl_cache_expiration():
    # Use a controllable timer
    current = [0.0]

    def fake_timer():
        return current[0]

    @cachefunc.ttl_cache(maxsize=2, ttl=5, timer=fake_timer)
    def double(x):
        return 2 * x

    # Cache two values
    assert double(1) == 2
    assert double(2) == 4
    cache_dict = double.cache  # type: ignore[attr-defined]
    assert len(cache_dict) == 2

    # Advance time beyond ttl
    current[0] += 6
    # Accessing should recompute and replace entries
    assert double(1) == 2
    assert double(2) == 4
    # Cache should still have two entries, but they are fresh
    assert len(double.cache) == 2


def test_unbounded_cache_when_maxsize_none():
    """When maxsize=None, the cache should be unbounded (no eviction)."""
    @cachefunc.lru_cache(maxsize=None)
    def identity(x):
        return x

    # Insert many distinct values
    for i in range(100):
        assert identity(i) == i

    # The underlying cache should contain all entries; we can inspect the wrapper's cache
    cache_dict = identity.cache  # type: ignore[attr-defined]
    assert isinstance(cache_dict, dict)
    assert len(cache_dict) == 100
    # Ensure that a previously cached value is still present (value check is sufficient)
    assert 42 in cache_dict.values()
