import threading
import warnings

import pytest

from cachetools._cachedmethod import _wrapper


def test_unlocked_caching_behaviour():
    """Basic caching without lock/condition/info."""
    cache = {}
    key = lambda self, x: x

    class C:
        def compute(self, x):
            return x * 2

    # apply the wrapper after class creation
    C.compute = _wrapper(C.compute, cache=lambda obj: cache, key=key)
    # ensure descriptor knows its attribute name
    C.compute.__set_name__(C, "compute")

    c = C()
    assert c.compute(2) == 4
    # second call with same argument should hit the cache
    assert c.compute(2) == 4
    # cache should contain a single entry
    assert cache == {2: 4}


def test_locked_caching_and_thread_safety():
    """Caching with a lock should be thread‑safe."""
    lock = threading.Lock()
    cache = {}
    key = lambda self, x: x

    class C:
        def compute(self, x):
            return x + 1

    C.compute = _wrapper(C.compute, cache=lambda obj: cache, key=key, lock=lambda obj: lock)
    C.compute.__set_name__(C, "compute")

    c = C()
    results = []

    def worker(val):
        results.append(c.compute(val))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # each result should be the input plus one
    assert sorted(results) == list(range(1, 6))
    # cache should contain all five entries
    assert cache == {i: i + 1 for i in range(5)}


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
    C.compute.__set_name__(C, "compute")

    c = C()
    # first call – miss
    assert c.compute(1) == 3
    # second distinct call – another miss
    assert c.compute(2) == 4
    # repeat first argument – hit
    assert c.compute(1) == 3

    # cache_info should report (size, hits, misses)
    size, hits, misses = c.compute.cache_info()
    assert size == 2  # two distinct keys cached
    assert hits == 1
    assert misses == 2


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
    # Manually set the descriptor name so that __set_name__ logic runs
    C.compute.__set_name__(C, "compute")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Access via the class returns the descriptor; call with the class explicitly
        wrapper = C.compute
        result = wrapper(C, 5)  # pass the class as the first argument
        assert result == 10
        # Two warnings: one for classmethod usage, one for the call itself
        assert any(issubclass(item.category, DeprecationWarning) for item in w)
        # Ensure the underlying method was called exactly once
        assert C.calls == 1


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
    C.compute.__set_name__(C, "compute")

    c = C()
    with pytest.raises(TypeError, match="No '__dict__' attribute"):
        c.compute(1)
