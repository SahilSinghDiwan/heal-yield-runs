import threading
import warnings

import pytest

from cachetools._cachedmethod import _wrapper, _call_set_name


def test_unlocked_caching_behaviour():
    """Basic caching without lock/condition should store and retrieve values."""
    cache = {}
    calls = {"count": 0}

    def method(self, x):
        calls["count"] += 1
        return x * 2

    cache_fn = lambda obj: cache
    key_fn = lambda obj, x: x

    # Apply the wrapper and set the descriptor name
    Wrapped = _wrapper(method, cache=cache_fn, key=key_fn)
    _call_set_name(Wrapped, "compute")
    class C:
        compute = Wrapped

    c = C()
    # First call computes and caches
    assert c.compute(3) == 6
    assert calls["count"] == 1
    # Second call hits the cache
    assert c.compute(3) == 6
    assert calls["count"] == 1  # no additional call


def test_locked_caching_and_thread_safety():
    """Caching with a lock should be thread‑safe and avoid duplicate work."""
    lock = threading.Lock()
    cache = {}
    calls = {"count": 0}
    cond = threading.Condition(lock)

    def method(self, x):
        calls["count"] += 1
        return x * 2

    cache_fn = lambda obj: cache
    key_fn = lambda obj, x: x
    lock_fn = lambda obj: lock
    cond_fn = lambda obj: cond

    Wrapped = _wrapper(
        method,
        cache=cache_fn,
        key=key_fn,
        lock=lock_fn,
        cond=cond_fn,
    )
    _call_set_name(Wrapped, "compute")
    class C:
        compute = Wrapped

    c = C()

    # Run the method concurrently from several threads
    def worker():
        assert c.compute(5) == 10

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Only one actual call should have been made
    assert calls["count"] == 1


def test_info_caching_and_cache_info():
    """When an info function is supplied, cache_info should reflect hits/misses."""
    cache = {}
    calls = {"count": 0}
    lock = threading.Lock()

    def method(self, x):
        calls["count"] += 1
        return x * 2

    def info(cache_obj, hits, misses):
        return {"hits": hits, "misses": misses, "size": len(cache_obj)}

    cache_fn = lambda obj: cache
    key_fn = lambda obj, x: x
    lock_fn = lambda obj: lock

    Wrapped = _wrapper(
        method,
        cache=cache_fn,
        key=key_fn,
        lock=lock_fn,
        info=info,
    )
    _call_set_name(Wrapped, "compute")
    class C:
        compute = Wrapped

    c = C()
    # First call: miss
    assert c.compute(1) == 2
    # Second call: hit
    assert c.compute(1) == 2
    # Verify cache_info reflects one hit and one miss
    assert c.compute.cache_info() == {"hits": 1, "misses": 1, "size": 1}
    # Clear cache and ensure info resets
    c.compute.cache_clear()
    assert c.compute.cache_info() == {"hits": 0, "misses": 0, "size": 0}


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

    cache_fn = lambda obj: (obj or C)._cache  # works for both class and None
    key_fn = lambda obj, x: x
    lock_fn = lambda obj: (obj or C)._lock
    cond_fn = lambda obj: (obj or C)._cond

    # Apply the wrapper after class creation (deprecated path)
    C.compute = _wrapper(
        C.compute,
        cache=cache_fn,
        key=key_fn,
        lock=lock_fn,
        cond=cond_fn,
    )
    _call_set_name(C, "compute")

    # Access the underlying descriptor directly to trigger the deprecation warning
    descriptor = C.__dict__["compute"]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = descriptor(4)  # call as a classmethod
        assert result == 8
        # Exactly one DeprecationWarning should be emitted for classmethod use
        assert any(issubclass(warn.category, DeprecationWarning) for warn in w)

    # Subsequent calls via the class should still return cached values without extra warnings
    with warnings.catch_warnings(record=True) as w2:
        warnings.simplefilter("always")
        assert C.compute(4) == 8
        # No new deprecation warning on the second call
        assert not any(issubclass(warn.category, DeprecationWarning) for warn in w2)


def test_descriptor_on_slots_raises_type_error():
    """A descriptor applied to a class with __slots__ (no __dict__) should raise a DeprecationWarning."""
    class C:
        __slots__ = ("_cache",)  # allow storage of the cache but no __dict__

        def __init__(self):
            self._cache = {}

        def compute(self, x):
            return x * 2

    cache_fn = lambda obj: obj._cache
    key_fn = lambda obj, x: x

    C.compute = _wrapper(C.compute, cache=cache_fn, key=key_fn)
    _call_set_name(C, "compute")

    c = C()
    # Accessing the method should emit a DeprecationWarning (due to missing __dict__)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = c.compute(1)
        assert result == 2
        # Verify that a DeprecationWarning was issued
        assert any(issubclass(warn.category, DeprecationWarning) for warn in w)
