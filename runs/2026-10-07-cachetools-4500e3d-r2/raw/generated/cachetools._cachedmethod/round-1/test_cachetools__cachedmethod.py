import threading
import warnings

import pytest

from cachetools import _cachedmethod


# Helper objects --------------------------------------------------------------

class DummyLock:
    """A no‑op context manager used as a lock."""
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def dummy_lock(_):
    return DummyLock()


def dummy_cond(_):
    """Condition that works with DummyLock."""
    return threading.Condition(DummyLock())


# -----------------------------------------------------------------------------


def test_unlocked_caches_and_counts():
    """Basic unlocked cache with hit/miss counting."""
    class Foo:
        def __init__(self):
            self._cache = {}

        def _method(self, x):
            return x * 2

        # use the internal _wrapper to create a cached method
        bar = _cachedmethod._wrapper(
            _method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=None,
            cond=None,
            info=lambda cache, hits, misses: (hits, misses),
        )

    f = Foo()

    # first call – miss
    assert f.bar(3) == 6
    assert f._cache == {3: 6}
    # cache_info is attached after the first call (descriptor replaces itself)
    assert f.bar.cache_info() == (0, 1)  # 0 hits, 1 miss

    # second call – hit
    assert f.bar(3) == 6
    assert f.bar.cache_info() == (1, 1)  # now 1 hit, 1 miss

    # clear the cache and verify counters reset
    f.bar.cache_clear()
    assert f._cache == {}
    assert f.bar.cache_info() == (0, 0)


def test_locked_caches_and_counts():
    """Locked cache (with a dummy lock) and hit/miss counting."""
    class Foo:
        def __init__(self):
            self._cache = {}

        def _method(self, x):
            return x + 5

        bar = _cachedmethod._wrapper(
            _method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=dummy_lock,
            cond=None,
            info=lambda cache, hits, misses: (hits, misses),
        )

    f = Foo()

    # first call – miss
    assert f.bar(10) == 15
    assert f._cache == {10: 15}
    assert f.bar.cache_info() == (0, 1)

    # second call – hit
    assert f.bar(10) == 15
    assert f.bar.cache_info() == (1, 1)

    # different argument – miss again
    assert f.bar(7) == 12
    assert f.bar.cache_info() == (1, 2)

    # clear cache
    f.bar.cache_clear()
    assert f._cache == {}
    assert f.bar.cache_info() == (0, 0)


def test_conditioned_caches_and_counts():
    """Cache with both a lock and a condition variable."""
    lock_obj = threading.Lock()
    lock = lambda _: lock_obj
    cond = lambda _: threading.Condition(lock_obj)

    class Foo:
        def __init__(self):
            self._cache = {}

        def _method(self, x):
            return x * x

        baz = _cachedmethod._wrapper(
            _method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lock,
            cond=cond,
            info=lambda cache, hits, misses: (hits, misses),
        )

    f = Foo()

    # first call – miss
    assert f.baz(4) == 16
    assert f._cache == {4: 16}
    assert f.baz.cache_info() == (0, 1)

    # second call – hit
    assert f.baz(4) == 16
    assert f.baz.cache_info() == (1, 1)

    # clear cache
    f.baz.cache_clear()
    assert f._cache == {}
    assert f.baz.cache_info() == (0, 0)


def test_class_access_returns_wrapper_with_cache_attribute():
    """Accessing the cached method via the class should return the wrapper
    (not the descriptor) and expose the injected ``cache`` attribute."""
    class Foo:
        def __init__(self):
            self._cache = {}

        def _method(self, x):
            return x - 1

        bar = _cachedmethod._wrapper(
            _method,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=dummy_lock,
            cond=None,
            info=None,
        )

    # Access via the class – should give the wrapper object
    wrapper = Foo.bar
    # The wrapper should have the ``cache`` attribute injected by _wrapper
    assert hasattr(wrapper, "cache")
    # ``cache`` should be the same callable we passed in
    assert wrapper.cache is (lambda self: self._cache)  # type: ignore

    # The wrapper itself is not callable (it needs an instance)
    with pytest.raises(TypeError):
        wrapper(1)  # type: ignore
