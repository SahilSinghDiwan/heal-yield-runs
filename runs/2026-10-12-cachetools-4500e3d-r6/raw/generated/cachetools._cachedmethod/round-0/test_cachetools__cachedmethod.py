import threading
import warnings

import pytest

from cachetools import _cachedmethod


def test_unlocked_wrapper_caches_and_reports_info():
    """Basic unlocked wrapper should cache results and expose cache_info."""
    class Foo:
        def __init__(self):
            self._cache = {}

        def compute(self, x):
            return x * 2

    # install the descriptor
    Foo.compute = _cachedmethod._wrapper(
        Foo.compute,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
        info=lambda cache, hits, misses: (len(cache), hits, misses),
    )

    f = Foo()
    # first call – miss
    assert f.compute(3) == 6
    assert f.compute.cache == {3: 6}
    assert f.compute.cache_info() == (1, 0, 1)  # size, hits, misses

    # second call – hit
    assert f.compute(3) == 6
    assert f.compute.cache_info() == (1, 1, 1)

    # clear cache
    f.compute.cache_clear()
    assert f.compute.cache == {}
    assert f.compute.cache_info() == (0, 0, 0)


def test_locked_wrapper_uses_lock_and_counts_hits():
    """Locked wrapper should protect the cache with a lock."""
    lock = threading.Lock()

    class Bar:
        def __init__(self):
            self._cache = {}

        def compute(self, x):
            return x + 10

    Bar.compute = _cachedmethod._wrapper(
        Bar.compute,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
        lock=lock,
        info=lambda cache, hits, misses: (len(cache), hits, misses),
    )

    b = Bar()
    # first call – miss
    assert b.compute(5) == 15
    assert isinstance(b.compute.cache_lock, threading.Lock)
    assert b.compute.cache_info() == (1, 0, 1)

    # second call – hit
    assert b.compute(5) == 15
    assert b.compute.cache_info() == (1, 1, 1)

    # clear cache
    b.compute.cache_clear()
    assert b.compute.cache == {}
    assert b.compute.cache_info() == (0, 0, 0)


def test_condition_and_lock_wrapper_behaves_correctly():
    """Wrapper with both lock and condition should still cache correctly."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    class Baz:
        def __init__(self):
            self._cache = {}

        def compute(self, x):
            return x * x

    Baz.compute = _cachedmethod._wrapper(
        Baz.compute,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
        lock=lock,
        cond=cond,
        info=lambda cache, hits, misses: (len(cache), hits, misses),
    )

    z = Baz()
    # first call – miss
    assert z.compute(4) == 16
    assert isinstance(z.compute.cache_lock, threading.Lock)
    assert isinstance(z.compute.cache_condition, threading.Condition)
    assert z.compute.cache_info() == (1, 0, 1)

    # second call – hit
    assert z.compute(4) == 16
    assert z.compute.cache_info() == (1, 1, 1)


def test_classmethod_deprecated_warning():
    """Using @cachedmethod on a classmethod should emit a DeprecationWarning."""
    class Qux:
        _cache = {}

        @classmethod
        def compute(cls, x):
            return x - 1

    Qux.compute = _cachedmethod._wrapper(
        Qux.compute,
        cache=lambda cls: cls._cache,
        key=lambda cls, x: x,
        info=lambda cache, hits, misses: (len(cache), hits, misses),
    )

    # Access via class – should warn on call
    with pytest.warns(DeprecationWarning):
        assert Qux.compute(10) == 9

    # Access via instance – also goes through the same wrapper and warns
    q = Qux()
    with pytest.warns(DeprecationWarning):
        assert q.compute(20) == 19

    # Cache should have been populated
    assert Qux._cache == {10: 9, 20: 19}


def test_descriptor_without_dict_raises_type_error():
    """Objects without a __dict__ (e.g., slots) should raise TypeError."""
    class NoDict:
        __slots__ = ()

        def compute(self, x):
            return x * 3

    NoDict.compute = _cachedmethod._wrapper(
        NoDict.compute,
        cache=lambda self: {},  # dummy cache, never used because we expect error earlier
        key=lambda self, x: x,
    )

    nd = NoDict()
    with pytest.raises(TypeError) as exc:
        nd.compute(2)
    assert "No '__dict__' attribute" in str(exc.value)


def test_descriptor_set_name_conflict_raises_type_error():
    """Assigning the same descriptor to two different attribute names should error."""
    class Conflict:
        def method(self, x):
            return x

    descriptor = _cachedmethod._wrapper(
        Conflict.method,
        cache=lambda self: {},
        key=lambda self, x: x,
    )
    Conflict.first = descriptor
    # The second assignment should trigger a TypeError during __set_name__
    with pytest.raises(TypeError) as exc:
        Conflict.second = descriptor
    assert "Cannot assign the same @cachedmethod to two different names" in str(exc.value)
