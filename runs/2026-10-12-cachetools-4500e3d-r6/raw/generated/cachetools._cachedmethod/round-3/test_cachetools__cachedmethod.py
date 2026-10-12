import threading
import warnings

import pytest

from cachetools import _cachedmethod


def test_condition_and_lock_wrapper_behaves_correctly():
    """Wrapper with both lock and condition should cache and report info correctly."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    # simple function to be wrapped
    def _func(self, x):
        return x * x

    class Baz:
        _cache = {}
        # use the internal _wrapper to create a descriptor with lock, condition and info
        compute = _cachedmethod._wrapper(
            _func,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lambda self: lock,          # lock must be a callable returning a lock
            cond=lambda self: cond,           # condition must be a callable returning a condition
            info=lambda cache, hits, misses: (len(cache), hits, misses),
        )

    b = Baz()
    # first call – miss
    assert b.compute(3) == 9
    # second call – hit
    assert b.compute(3) == 9
    # cache info should reflect one hit and one miss, and cache size 1
    assert b.compute.cache_info() == (1, 1, 1)
    # clearing cache resets counters
    b.compute.cache_clear()
    assert b.compute.cache_info() == (0, 0, 0)


def test_classmethod_deprecated_warning():
    """Using @cachedmethod on a classmethod should emit a DeprecationWarning."""
    def _func(cls, x):
        return x - 1

    class Qux:
        _cache = {}
        # No lock/cond/info -> deprecated classmethod handling path
        compute = _cachedmethod._wrapper(
            _func,
            cache=lambda cls: cls._cache,
            key=lambda cls, x: x,
        )

    # Access the descriptor directly from the class dict to invoke the
    # deprecated __call__ path (which expects the class as first argument).
    descriptor = Qux.__dict__['compute']

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        result = descriptor(Qux, 5)  # invoke as classmethod
        assert result == 4
        # The first warning should be about deprecated classmethod usage.
        assert any("decorating class methods" in str(wi.message) for wi in w)


def test_descriptor_without_dict_warns_and_works():
    """Objects without a __dict__ (e.g., slots) should emit a DeprecationWarning but still work."""
    def _func(self, x):
        return x * 3

    class NoDict:
        __slots__ = ()
        compute = _cachedmethod._wrapper(
            _func,
            cache=lambda self: {},  # dummy cache
            key=lambda self, x: x,
        )

    nd = NoDict()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        # The call should succeed and produce the expected result.
        assert nd.compute(2) == 6
        # A deprecation warning about missing __dict__ should be emitted.
        assert any("No '__dict__' attribute" in str(wi.message) for wi in w)


def test_descriptor_set_name_conflict_raises_type_error():
    """Assigning the same descriptor to two different attribute names raises TypeError."""
    def _func(self, x):
        return x

    descriptor = _cachedmethod._wrapper(
        _func,
        cache=lambda self: {},
        key=lambda self, x: x,
    )

    class Foo:
        a = descriptor

    # Attempt to reuse the same descriptor instance under a different name in a subclass.
    with pytest.raises(TypeError):
        class Bar(Foo):
            b = descriptor
