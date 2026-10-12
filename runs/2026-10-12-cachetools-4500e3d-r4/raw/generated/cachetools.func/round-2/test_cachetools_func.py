import pytest
import types

import cachetools.func as func


def test_fifo_cache_eviction():
    @func.fifo_cache(maxsize=2)
    def identity(x):
        return x

    # Fill cache beyond its maxsize
    assert identity(1) == 1  # miss
    assert identity(2) == 2  # miss
    info = identity.cache_info()
    assert info.currsize == 2

    # This should cause eviction of the oldest entry (1)
    assert identity(3) == 3  # miss
    info = identity.cache_info()
    assert info.currsize == 2

    # Re-accessing 2 should be a hit, 1 should be a miss (evicted)
    assert identity(2) == 2  # hit
    assert identity(1) == 1  # miss (recomputed)
    info = identity.cache_info()
    assert info.hits >= 1
    assert info.misses >= 3


def test_lru_cache_eviction():
    @func.lru_cache(maxsize=2)
    def identity(x):
        return x

    assert identity(1) == 1
    assert identity(2) == 2
    info = identity.cache_info()
    assert info.currsize == 2

    # Access 1 to make it most-recently used
    assert identity(1) == 1
    # Adding a new entry should evict 2 (least recently used)
    assert identity(3) == 3
    info = identity.cache_info()
    assert info.currsize == 2

    # 2 should be a miss now
    assert identity(2) == 2
    info = identity.cache_info()
    assert info.misses >= 3
    assert info.hits >= 1


def test_lfu_cache_eviction():
    @func.lfu_cache(maxsize=2)
    def identity(x):
        return x

    # Populate cache
    assert identity(1) == 1
    assert identity(2) == 2
    # Access 1 multiple times to increase its frequency
    for _ in range(3):
        assert identity(1) == 1
    # Adding a new entry should evict the least-frequently used (2)
    assert identity(3) == 3
    info = identity.cache_info()
    assert info.currsize == 2

    # 2 should be a miss now
    assert identity(2) == 2
    info = identity.cache_info()
    assert info.misses >= 2
    assert info.hits >= 3


def test_rr_cache_deterministic_eviction():
    # Use a deterministic choice function that always selects the first key
    def first_choice(seq):
        return seq[0]

    @func.rr_cache(maxsize=2, choice=first_choice)
    def identity(x):
        return x

    assert identity(1) == 1
    assert identity(2) == 2
    # Adding a third entry will evict the first key (1) due to our choice function
    assert identity(3) == 3
    info = identity.cache_info()
    assert info.currsize == 2

    # 1 should be a miss now
    assert identity(1) == 1
    info = identity.cache_info()
    assert info.misses >= 2
    assert info.hits >= 1


def test_ttl_cache_expiration():
    # Use a controllable timer
    current = [0.0]

    def fake_timer():
        return current[0]

    @func.ttl_cache(maxsize=2, ttl=5, timer=fake_timer)
    def identity(x):
        return x

    # Populate cache
    assert identity(1) == 1
    assert identity(2) == 2
    info = identity.cache_info()
    assert info.currsize == 2

    # Advance time within TTL: should be hits
    current[0] += 4
    assert identity(1) == 1
    assert identity(2) == 2
    info = identity.cache_info()
    assert info.hits >= 2

    # Advance beyond TTL: entries should expire
    current[0] += 2
    assert identity(1) == 1  # recomputed
    assert identity(2) == 2  # recomputed
    info = identity.cache_info()
    assert info.misses >= 2


def test_typed_cache_distinguishes_types():
    @func.lru_cache(maxsize=2, typed=True)
    def identity(x):
        return x

    # 1 (int) and 1.0 (float) should be cached separately
    assert identity(1) == 1
    assert identity(1.0) == 1.0
    info = identity.cache_info()
    assert info.currsize == 2

    # Re-access should be hits for each distinct type
    assert identity(1) == 1
    assert identity(1.0) == 1.0
    info = identity.cache_info()
    assert info.hits >= 2


def test_decorator_without_parentheses():
    # Using the decorator directly without parentheses should work
    @func.lru_cache
    def identity(x):
        """Return the argument unchanged."""
        return x

    assert identity.__doc__ == "Return the argument unchanged."
    assert identity(10) == 10
    info = identity.cache_info()
    assert info.currsize == 1
    # Second call should be a hit
    assert identity(10) == 10
    info = identity.cache_info()
    assert info.hits >= 1


def test_unbounded_cache_behaviour():
    @func.lru_cache(maxsize=None)
    def identity(x):
        return x

    # Populate with more items than a typical bounded cache
    for i in range(10):
        assert identity(i) == i

    info = identity.cache_info()
    # For an unbounded cache, currsize should reflect all inserted items
    assert info.currsize == 10
    # Ensure that hits increase when re-accessing values
    for i in range(10):
        assert identity(i) == i
    info = identity.cache_info()
    assert info.hits >= 10
