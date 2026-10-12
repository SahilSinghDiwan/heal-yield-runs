import builtins
import threading
import warnings

import pytest

from cachetools._cachedmethod import _wrapper, _warn_classmethod, _warn_instance_dict


def make_unlocked_class():
    """Create a class using the unlocked (no lock, no info) wrapper."""
    class C:
        def __init__(self):
            self._cache = {}
            self.calls = 0

        def compute(self, x):
            self.calls += 1
            return x * 10

    # cache function returns the per‑instance dict
    cache_fn = lambda obj: obj._cache
    # key function uses the argument directly
    key_fn = lambda obj, x: x

    C.compute = _wrapper(C.compute, cache=cache_fn, key=key_fn)
    return C


def make_locked_class():
    """Create a class using the locked wrapper (no info)."""
    lock = threading.Lock()

    class C:
        def __init__(self):
            self._cache = {}
            self._lock = lock
            self.calls = 0

        def compute(self, x):
            self.calls += 1
            return x + 5

    cache_fn = lambda obj: obj._cache
    key_fn = lambda obj, x: x
    lock_fn = lambda obj: obj._lock

    C.compute = _wrapper(C.compute, cache=cache_fn, key=key_fn, lock=lock_fn)
    return C


def make_info_class():
    """Create a class using the unlocked wrapper with an info function."""
    def info(cache, hits, misses):
        # Return a tuple that is easy to assert on
        return (len(cache), hits, misses)

    class C:
        def __init__(self):
            self._cache = {}
            self.calls = 0

        def compute(self, x):
            self.calls += 1
            return x * 3

    cache_fn = lambda obj: obj._cache
    key_fn = lambda obj, x: x

    C.compute = _wrapper(C.compute, cache=cache_fn, key=key_fn, info=info)
    return C


def test_unlocked_caching_behaviour():
    C = make_unlocked_class()
    c = C()

    # first call: not cached
    assert c.compute(2) == 20
    assert c.calls == 1
    # second call with same argument: cached, no extra call
    assert c.compute(2) == 20
    assert c.calls == 1
    # different argument: new computation
    assert c.compute(3) == 30
    assert c.calls == 2

    # cache content should reflect both keys
    assert c._cache == {2: 20, 3: 30}


def test_locked_caching_and_thread_safety():
    C = make_locked_class()
    c = C()

    # first call populates cache
    assert c.compute(7) == 12
    assert c.calls == 1
    # second call hits cache
    assert c.compute(7) == 12
    assert c.calls == 1

    # ensure lock attribute is used (no exception means lock worked)
    assert isinstance(c._lock, threading.Lock)

    # cache should contain the computed value
    assert c._cache == {7: 12}


def test_info_caching_and_cache_info():
    C = make_info_class()
    c = C()

    # No hits yet, two misses after two distinct calls
    assert c.compute(1) == 3
    assert c.compute(2) == 6
    # cache_info should report 2 entries, 0 hits, 2 misses
    assert c.compute.cache_info() == (2, 0, 2)

    # Re‑call a cached key: hits increase
    assert c.compute(1) == 3
    assert c.compute.cache_info() == (2, 1, 2)

    # Clear cache and verify counters reset
    c.compute.cache_clear()
    assert c._cache == {}
    assert c.compute.cache_info() == (0, 0, 0)


def test_deprecated_classmethod_warning():
    lock = threading.Lock()
    cond = threading.Condition(lock)

    class C:
        _cache = {}
        _lock = lock
        _cond = cond
        calls = 0

        @classmethod
        def compute(cls, x):
            cls.calls += 1
            return x * 2

    # Build a descriptor that would be used for a classmethod (no info)
    cache_fn = lambda obj: obj._cache
    key_fn = lambda obj, x: x
    lock_fn = lambda obj: obj._lock
    cond_fn = lambda obj: obj._cond

    # Using both lock and condition triggers the deprecated path
    C.compute = _wrapper(C.compute, cache=cache_fn, key=key_fn, lock=lock_fn, cond=cond_fn)

    # Access via the class should raise a DeprecationWarning (from __init__ of _WrapperBase)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Accessing the descriptor through the class returns the wrapper (obj=None)
        wrapper = C.compute
        # Calling it as a classmethod should also warn
        result = wrapper(5)
        assert result == 10
        # Two warnings: one from _warn_classmethod in _WrapperBase, one from __call__
        assert any(issubclass(wi.category, DeprecationWarning) for wi in w)

    # Ensure the underlying class counter was incremented exactly once
    assert C.calls == 1


def test_descriptor_on_slots_raises_type_error():
    class C:
        __slots__ = ()  # no __dict__

        def __init__(self):
            self._cache = {}

        def compute(self, x):
            return x

    cache_fn = lambda obj: obj._cache
    key_fn = lambda obj, x: x

    C.compute = _wrapper(C.compute, cache=cache_fn, key=key_fn)

    c = C()
    # Accessing the method should raise TypeError because the instance has no __dict__
    with pytest.raises(TypeError) as exc:
        c.compute(1)
    assert "No '__dict__' attribute" in str(exc.value)
