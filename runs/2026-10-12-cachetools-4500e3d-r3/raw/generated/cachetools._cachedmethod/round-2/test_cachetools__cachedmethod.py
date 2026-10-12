import builtins
import threading
import warnings

import pytest

from cachetools._cachedmethod import _wrapper


def _call_set_name(cls, name):
    """Helper to invoke __set_name__ on the descriptor stored in the class dict."""
    descriptor = cls.__dict__[name]
    descriptor.__set_name__(cls, name)


def test_unlocked_caching_behaviour():
    """Basic caching without lock/condition/info."""
    cache = {}
    key = lambda self, x: x

    class C:
        def compute(self, x):
            return x * 2

    # Apply the wrapper after class creation
    C.compute = _wrapper(C.compute, cache=lambda obj: cache, key=key)
    _call_set_name(C, "compute")

    c = C()
    # first call populates cache
    assert c.compute(3) == 6
    assert cache[3] == 6
    # second call hits cache
    assert c.compute(3) == 6
    # cache unchanged
    assert len(cache) == 1


def test_locked_caching_and_thread_safety():
    """Caching with a lock should be thread‑safe."""
    lock = threading.Lock()
    cache = {}
    key = lambda self, x: x

    class C:
        def compute(self, x):
            return x + 1

    C.compute = _wrapper(
        C.compute, cache=lambda obj: cache, key=key, lock=lambda obj: lock
    )
    _call_set_name(C, "compute")

    c = C()
    # Simulate concurrent access by calling from multiple threads
    results = []

    def worker(val):
        results.append(c.compute(val))

    threads = [threading.Thread(target=worker, args=(5,)) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All results should be identical and cache should contain a single entry
    assert results == [6] * 5
    assert cache[5] == 6
    assert len(cache) == 1


def test_info_caching_and_cache_info():
    """Caching with an info function should expose hit/miss statistics."""
    cache = {}
    key = lambda self, x: x
    info = lambda c, hits, misses: (len(c), hits, misses)

    class C:
        def compute(self, x):
            return x + 2

    C.compute = _wrapper(
        C.compute,
        cache=lambda obj: cache,
        key=key,
        info=info,
    )
    _call_set_name(C, "compute")

    c = C()
    # first call: miss
    assert c.compute(1) == 3
    # second call: hit
    assert c.compute(1) == 3
    # cache_info should reflect 1 hit, 1 miss, and cache size 1
    assert c.compute.cache_info() == (1, 1, 1)


def test_deprecated_classmethod_warning():
    """Using @cachedmethod on a classmethod should emit DeprecationWarnings."""
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

    cache_fn = lambda obj: obj._cache
    key_fn = lambda obj, x: x
    lock_fn = lambda obj: obj._lock
    cond_fn = lambda obj: obj._cond

    # Apply the wrapper after class creation (deprecated path)
    C.compute = _wrapper(
        C.compute,
        cache=cache_fn,
        key=key_fn,
        lock=lock_fn,
        cond=cond_fn,
    )
    _call_set_name(C, "compute")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # First call should trigger the deprecation warning for classmethod use
        result = C.compute(4)
        assert result == 8
        # Two warnings: one for decorating classmethod, one for using it
        assert any(isinstance(wi.message, DeprecationWarning) for wi in w)

    # Ensure the underlying method was called exactly once
    assert C.calls == 1
    # Cache should contain the result
    assert C._cache[4] == 8


def test_descriptor_on_slots_raises_type_error():
    """A descriptor applied to a class with __slots__ (no __dict__) should raise TypeError."""
    class C:
        __slots__ = ("_cache",)  # allow storage of the cache but no __dict__

        def __init__(self):
            self._cache = {}

        def compute(self, x):
            return x

    cache_fn = lambda obj: obj._cache
    key_fn = lambda obj, x: x

    C.compute = _wrapper(C.compute, cache=cache_fn, key=key_fn)
    # __set_name__ should be called; the subsequent attribute access will raise
    _call_set_name(C, "compute")

    c = C()
    # Accessing the method should raise TypeError because the instance lacks __dict__
    with pytest.raises(TypeError):
        c.compute(1)
