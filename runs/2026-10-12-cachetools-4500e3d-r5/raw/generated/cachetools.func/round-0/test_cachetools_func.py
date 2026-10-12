import pytest
import time

import cachetools.func as func_mod
from cachetools import TTLCache


def test_lru_cache_eviction_and_order():
    """LRU cache should evict the least‑recently used entry when full."""
    calls = []

    @func_mod.lru_cache(maxsize=2)
    def f(x):
        calls.append(x)
        return x * 10

    # Fill the cache
    assert f(1) == 10
    assert f(2) == 20
    assert calls == [1, 2]

    # Access 1 again – makes it most‑recent
    assert f(1) == 10
    assert calls == [1, 2]  # no new call

    # Insert a new key, evicting the least‑recently used (2)
    assert f(3) == 30
    assert calls == [1, 2, 3]

    # 2 was evicted, so a new call is required
    assert f(2) == 20
    assert calls == [1, 2, 3, 2]


def test_typed_cache_separates_int_and_float():
    """When typed=True, int and float arguments are cached separately."""
    calls = []

    @func_mod.lru_cache(maxsize=2, typed=True)
    def g(x):
        calls.append(x)
        return x

    assert g(1) == 1
    assert g(1.0) == 1.0
    # Both calls should be recorded because the keys differ by type
    assert calls == [1, 1.0]
    # Re‑calling with the same values should hit the cache (no new calls)
    assert g(1) == 1
    assert g(1.0) == 1.0
    assert calls == [1, 1.0]


def test_ttl_cache_with_custom_timer():
    """TTL cache should expire entries after the given ttl using the supplied timer."""
    timer = [0.0]

    def mytimer():
        return timer[0]

    calls = []

    @func_mod.ttl_cache(maxsize=None, ttl=5, timer=mytimer)
    def h(x):
        calls.append(x)
        return x + 1

    # First call – cache miss
    assert h(10) == 11
    assert calls == [10]

    # Within ttl – cache hit
    timer[0] = 3
    assert h(10) == 11
    assert calls == [10]

    # After ttl – cache miss again
    timer[0] = 6
    assert h(10) == 11
    assert calls == [10, 10]


def test_rr_cache_deterministic_replacement():
    """RR cache with a deterministic choice function should replace the expected entry."""
    # deterministic choice: always pick the first key in the internal sequence
    def first_choice(seq):
        return seq[0]

    calls = []

    @func_mod.rr_cache(maxsize=2, choice=first_choice)
    def f(x):
        calls.append(x)
        return x

    # Fill the cache
    assert f(1) == 1
    assert f(2) == 2
    assert calls == [1, 2]

    # Insert third key – should evict the first inserted key (1)
    assert f(3) == 3
    assert calls == [1, 2, 3]

    # Access 1 again – it was evicted, so a new call occurs
    assert f(1) == 1
    assert calls == [1, 2, 3, 1]


def test_decorator_without_parentheses():
    """The cache decorators should work when used without explicit parentheses."""
    calls = []

    @func_mod.lru_cache
    def inc(x):
        calls.append(x)
        return x + 1

    # First call – cache miss
    assert inc(5) == 6
    assert calls == [5]

    # Second call with same argument – cache hit
    assert inc(5) == 6
    assert calls == [5]  # no additional call


def test_cache_parameters_reflect_configuration():
    """The wrapper should expose its cache parameters via cache_parameters()."""
    @func_mod.lru_cache(maxsize=10, typed=True)
    def f(x):
        return x

    params = f.cache_parameters()
    assert params == {"maxsize": 10, "typed": True}

    @func_mod.lru_cache(maxsize=None)
    def g(x):
        return x

    params_none = g.cache_parameters()
    assert params_none["maxsize"] is None
    assert params_none["typed"] is False
