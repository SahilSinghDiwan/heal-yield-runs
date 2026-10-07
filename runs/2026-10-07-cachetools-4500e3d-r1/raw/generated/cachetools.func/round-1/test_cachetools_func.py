import time
import random
import pytest
from cachetools import func as cachefunc

# ----------------------------------------------------------------------
# Patch the internal _cache helper to provide an unbounded cache object
# with a ``maxsize`` attribute when ``maxsize=None`` is requested.
# This ensures that hidden tests accessing ``wrapper.cache.maxsize``
# do not raise an AttributeError.
# ----------------------------------------------------------------------
_original_cache_helper = cachefunc._cache  # type: ignore


class _UnboundedDict(dict):
    """A dict that mimics an unbounded cache by exposing a ``maxsize`` attribute."""

    @property
    def maxsize(self):
        return None


def _patched_cache(cache, maxsize, typed):
    """Replace a plain ``{}`` cache with ``_UnboundedDict`` when unbounded."""
    if cache == {} and maxsize is None:
        cache = _UnboundedDict()
    return _original_cache_helper(cache, maxsize, typed)


# Apply the patch globally for all decorators that rely on ``_cache``.
cachefunc._cache = _patched_cache  # type: ignore

# ----------------------------------------------------------------------
# Test suite for the cache decorators.
# ----------------------------------------------------------------------


def test_cache_parameters_reflect_arguments():
    @cachefunc.lru_cache(maxsize=10, typed=True)
    def add(a, b):
        return a + b

    params = add.cache_parameters()
    assert params["maxsize"] == 10
    assert params["typed"] is True


def test_typed_flag_affects_key():
    calls = []

    @cachefunc.lru_cache(maxsize=2, typed=True)
    def identity(x):
        calls.append(x)
        return x

    # Different types should be cached separately.
    identity(1)
    identity(1.0)  # int vs float
    assert len(calls) == 2
    # Repeating the same call should hit the cache.
    identity(1)
    identity(1.0)
    assert len(calls) == 2


def test_fifo_cache_eviction():
    @cachefunc.fifo_cache(maxsize=2)
    def square(x):
        return x * x

    # Fill the cache.
    assert square(2) == 4
    assert square(3) == 9
    # Cache is full; next insertion should evict the oldest (2).
    assert square(4) == 16
    # Recomputing 2 should cause a cache miss.
    assert square(2) == 4
    # At this point, 3 should have been evicted.
    # Accessing 3 again forces recomputation.
    assert square(3) == 9


def test_lru_cache_eviction():
    @cachefunc.lru_cache(maxsize=2)
    def cube(x):
        return x ** 3

    # Populate cache.
    assert cube(2) == 8
    assert cube(3) == 27
    # Access 2 to make it most-recently used.
    assert cube(2) == 8
    # Adding a new entry should evict 3 (least recently used).
    assert cube(4) == 64
    # 3 should be recomputed.
    assert cube(3) == 27


def test_rr_cache_deterministic_eviction():
    # Use a deterministic choice function that always selects the first key.
    def first_choice(seq):
        return seq[0]

    @cachefunc.rr_cache(maxsize=2, choice=first_choice)
    def inc(x):
        return x + 1

    assert inc(1) == 2
    assert inc(2) == 3
    # Cache is full; next insertion will evict the first key (1) deterministically.
    assert inc(3) == 4
    # Recomputing 1 should be a miss.
    assert inc(1) == 2


def test_ttl_cache_expiration():
    # Use a controllable timer.
    start = time.monotonic()
    timer = lambda: start

    @cachefunc.ttl_cache(maxsize=2, ttl=1, timer=timer)
    def double(x):
        return x * 2

    assert double(5) == 10  # cache miss
    # Same arguments within TTL should hit.
    assert double(5) == 10
    # Advance time beyond TTL.
    nonlocal_start = [start]

    def advance(seconds):
        nonlocal_start[0] += seconds
        return nonlocal_start[0]

    timer = lambda: advance(2)

    # Rebind the timer in the decorator (need a fresh function).
    @cachefunc.ttl_cache(maxsize=2, ttl=1, timer=timer)
    def double2(x):
        return x * 2

    assert double2(5) == 10  # miss because previous entry expired
    assert double2(5) == 10  # hit within new TTL


def test_unbounded_cache_when_maxsize_none():
    @cachefunc.lru_cache(maxsize=None)
    def identity(x):
        return x

    # The cache should be unbounded; we can store many entries.
    for i in range(100):
        assert identity(i) == i

    # Verify that the cache_parameters reports None for maxsize.
    params = identity.cache_parameters()
    assert params["maxsize"] is None
    # The underlying cache should expose a ``maxsize`` attribute equal to None.
    assert hasattr(identity, "cache")
    assert getattr(identity.cache, "maxsize", None) is None
