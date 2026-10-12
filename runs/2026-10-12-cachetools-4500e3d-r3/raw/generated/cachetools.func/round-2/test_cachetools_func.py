import time
import types
import pytest

# Import the decorators from the module under test
from cachetools import func as cachefunc


def test_basic_caching_decorator():
    """Ensure that a simple cached function only computes once per argument."""
    calls = {"count": 0}

    @cachefunc.lru_cache(maxsize=32)
    def add_one(x):
        calls["count"] += 1
        return x + 1

    # First call computes
    assert add_one(1) == 2
    assert calls["count"] == 1
    # Second call with same arg hits cache
    assert add_one(1) == 2
    assert calls["count"] == 1
    # Different arg computes again
    assert add_one(2) == 3
    assert calls["count"] == 2


def test_maxsize_eviction_lru():
    """LRU cache should evict the least recently used entry when maxsize is exceeded."""
    calls = {"count": 0}

    @cachefunc.lru_cache(maxsize=2)
    def square(x):
        calls["count"] += 1
        return x * x

    # Fill cache with two entries
    assert square(2) == 4
    assert square(3) == 9
    assert calls["count"] == 2

    # Access one of them to make it most-recently used
    assert square(2) == 4
    assert calls["count"] == 2  # cache hit

    # Add a third entry, causing eviction of the least-recently used (3)
    assert square(4) == 16
    assert calls["count"] == 3

    # 3 should be recomputed (evicted)
    assert square(3) == 9
    assert calls["count"] == 4


def test_fifo_eviction_order():
    """FIFO cache should evict entries in insertion order."""
    calls = {"count": 0}

    @cachefunc.fifo_cache(maxsize=2)
    def inc(x):
        calls["count"] += 1
        return x + 1

    # Insert two entries
    assert inc(1) == 2
    assert inc(2) == 3
    assert calls["count"] == 2

    # Insert third entry, first inserted (1) should be evicted
    assert inc(3) == 4
    assert calls["count"] == 3

    # Re-calling with 1 forces recomputation
    assert inc(1) == 2
    assert calls["count"] == 4


def test_rr_cache_with_deterministic_choice():
    """RR cache should use the provided choice function for eviction."""
    calls = {"count": 0}
    # Deterministic choice: always evict the first key in the internal list
    deterministic_choice = lambda seq: seq[0]

    @cachefunc.rr_cache(maxsize=2, choice=deterministic_choice)
    def mul(x, y):
        calls["count"] += 1
        return x * y

    # Fill cache
    assert mul(2, 3) == 6
    assert mul(3, 4) == 12
    assert calls["count"] == 2

    # Adding a third entry should evict the first inserted (2,3)
    assert mul(5, 5) == 25
    assert calls["count"] == 3

    # (2,3) must be recomputed
    assert mul(2, 3) == 6
    assert calls["count"] == 4


def test_ttl_cache_expiration():
    """TTL cache should expire entries after the given ttl using a custom timer."""
    calls = {"count": 0}
    # Custom timer that we can control
    class FakeTimer:
        def __init__(self):
            self.now = 0.0

        def __call__(self):
            return self.now

        def advance(self, seconds):
            self.now += seconds

    timer = FakeTimer()

    @cachefunc.ttl_cache(maxsize=2, ttl=5, timer=timer)
    def greet(name):
        calls["count"] += 1
        return f"Hello, {name}!"

    # First call caches result
    assert greet("Alice") == "Hello, Alice!"
    assert calls["count"] == 1

    # Within ttl, should hit cache
    timer.advance(3)
    assert greet("Alice") == "Hello, Alice!"
    assert calls["count"] == 1

    # After ttl expires, should recompute
    timer.advance(3)  # total 6 > ttl
    assert greet("Alice") == "Hello, Alice!"
    assert calls["count"] == 2


def test_none_maxsize_disables_caching():
    """When maxsize=None, the decorator should not cache results."""
    calls = {"count": 0}

    @cachefunc.lru_cache(maxsize=None)
    def double(x):
        calls["count"] += 1
        return x * 2

    # Each call should compute anew
    assert double(5) == 10
    assert calls["count"] == 1
    assert double(5) == 10
    assert calls["count"] == 2
    assert double(6) == 12
    assert calls["count"] == 3


def test_typed_flag_separates_int_and_bool():
    """Typed flag should treat int and bool arguments as distinct keys."""
    calls = {"count": 0}

    @cachefunc.lru_cache(maxsize=32, typed=True)
    def identity(x):
        calls["count"] += 1
        return x

    # bool is a subclass of int, but typed=True should separate them
    assert identity(True) is True
    assert calls["count"] == 1
    # Cached hit for True
    assert identity(True) is True
    assert calls["count"] == 1
    # int 1 is a different key
    assert identity(1) == 1
    assert calls["count"] == 2
    # Cached hit for int 1
    assert identity(1) == 1
    assert calls["count"] == 2


def test_cache_parameters_attribute():
    """Each wrapper should expose cache_parameters() returning its configuration."""
    @cachefunc.lru_cache(maxsize=10, typed=False)
    def foo(x):
        return x

    params = foo.cache_parameters()
    assert isinstance(params, dict)
    assert params["maxsize"] == 10
    assert params["typed"] is False

    @cachefunc.lru_cache(maxsize=None, typed=True)
    def bar(x):
        return x

    params = bar.cache_parameters()
    assert params["maxsize"] is None
    assert params["typed"] is True


def test_wrapper_has_wrapped_attribute():
    """The wrapper returned by the decorator should preserve the original function via __wrapped__."""
    def original(a, b):
        return a + b

    wrapped = cachefunc.lru_cache()(original)
    # __wrapped__ should point to the original function
    assert isinstance(wrapped, types.FunctionType)
    assert wrapped.__wrapped__ is original
    # Behavior should be unchanged
    assert wrapped(2, 3) == 5
