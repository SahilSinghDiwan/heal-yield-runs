import threading
import warnings

import pytest

import cachetools._cachedmethod as _cachedmethod


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
            lock=lock,
            cond=cond,
            info=lambda cache, hits, misses: (len(cache), hits, misses),
        )

    b = Baz()
    # first call – miss
    assert b.compute(3) == 9
    # second call – hit
    assert b.compute(3) == 9
    # different argument – miss
    assert b.compute(4) == 16

    # The wrapper object is stored in the instance dict after first access
    wrapper = b.__dict__["compute"]
    # cache should contain two entries
    assert wrapper.cache == {3: 9, 4: 16}
    # cache_info should reflect 2 hits (second call to 3) and 2 misses (first 3 and first 4)
    assert wrapper.cache_info() == (2, 2, 2)

    # clearing the cache resets hits/misses
    wrapper.cache_clear()
    assert wrapper.cache == {}
    assert wrapper.cache_info() == (0, 0, 0)


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

    # Access via class should give the descriptor itself; calling it should warn
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        result = Qux.compute(5)  # invokes the descriptor's __call__
        assert result == 4
        # At least one DeprecationWarning should have been raised
        assert any(isinstance(item.message, DeprecationWarning) for item in w)

    # Also ensure that calling via an instance works and caches correctly
    q = Qux()
    assert q.compute(6) == 5
    # second call should hit the cache (no additional warning)
    with warnings.catch_warnings(record=True) as w2:
        warnings.simplefilter("always", DeprecationWarning)
        assert q.compute(6) == 5
        assert not w2  # no new warnings on instance calls


def test_descriptor_without_dict_raises_type_error():
    """Objects without a __dict__ (e.g., slots) should raise TypeError when cached."""
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
    with pytest.raises(TypeError) as exc:
        nd.compute(2)
    # The error message should mention '__dict__' and the class name
    assert "__dict__" in str(exc.value)
    assert "NoDict" in str(exc.value)


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
        # Attempt to assign the same descriptor instance to a different name
        with pytest.raises(TypeError):
            b = descriptor
