import threading
import warnings

import pytest

from cachetools import _cachedmethod


def test_unlocked_caches_results_and_info():
    """Basic unlocked wrapper should cache results and report hits/misses."""

    def compute(self, x):
        return x * 2

    class Foo:
        _cache = {}
        compute = _cachedmethod._wrapper(
            compute,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            info=lambda cache, hits, misses: (len(cache), hits, misses),
        )

    f = Foo()
    # first call – miss
    assert f.compute(3) == 6
    # second call – hit
    assert f.compute(3) == 6
    # third call with different argument – miss
    assert f.compute(4) == 8

    length, hits, misses = f.compute.cache_info()
    assert length == 2  # two distinct keys cached
    assert hits == 1    # one hit on the second call
    assert misses == 2  # two misses for the first calls of each key


def test_locked_caches_and_thread_safety():
    """Locked wrapper should cache correctly even when accessed from multiple threads."""

    lock = threading.Lock()

    def compute(self, x):
        return x + 5

    class Bar:
        _cache = {}
        compute = _cachedmethod._wrapper(
            compute,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lock,
            info=lambda cache, hits, misses: (len(cache), hits, misses),
        )

    b = Bar()
    results = []

    def worker(val):
        results.append(b.compute(val))

    threads = [threading.Thread(target=worker, args=(10,)) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads should get the same result
    assert results == [15] * 5
    length, hits, misses = b.compute.cache_info()
    assert length == 1
    assert hits == 4  # after the first miss, the rest are hits
    assert misses == 1


def test_condition_and_lock_wrapper_behaves_correctly():
    """Wrapper with both lock and condition should still cache correctly."""

    lock = threading.Lock()
    cond = threading.Condition(lock)

    def compute(self, x):
        return x * x

    class Baz:
        _cache = {}
        compute = _cachedmethod._wrapper(
            compute,
            cache=lambda self: self._cache,
            key=lambda self, x: x,
            lock=lock,
            cond=cond,
            info=lambda cache, hits, misses: (len(cache), hits, misses),
        )

    z = Baz()
    # first call – miss
    assert z.compute(4) == 16
    # second call – hit
    assert z.compute(4) == 16
    # different argument – miss
    assert z.compute(5) == 25

    length, hits, misses = z.compute.cache_info()
    assert length == 2
    assert hits == 1
    assert misses == 2


def test_classmethod_deprecated_warning():
    """Using @cachedmethod on a classmethod should emit a DeprecationWarning."""

    def compute(cls, x):
        return x - 1

    class Qux:
        _cache = {}
        compute = _cachedmethod._wrapper(
            compute,
            cache=lambda cls: cls._cache,
            key=lambda cls, x: x,
        )  # no info -> deprecated classmethod handling

    # Access via class – should warn on call
    with pytest.warns(DeprecationWarning):
        assert Qux.compute(10) == 9

    # Subsequent call should still be cached (hits increase)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert Qux.compute(10) == 9

    # Verify that the cache contains the result
    assert Qux._cache == {10: 9}


def test_descriptor_without_dict_raises_type_error():
    """Objects without a __dict__ (e.g., slots) should raise TypeError when cached."""

    def compute(self, x):
        return x * 3

    class NoDict:
        __slots__ = ()
        compute = _cachedmethod._wrapper(
            compute,
            cache=lambda self: {},  # dummy cache
            key=lambda self, x: x,
        )

    nd = NoDict()
    with pytest.raises(TypeError) as exc:
        nd.compute(2)
    # Ensure the message mentions '__dict__' to confirm the correct path
    assert "__dict__" in str(exc.value)


def test_descriptor_set_name_conflict_raises_type_error():
    """Assigning the same descriptor to two different attribute names should error."""

    def identity(self, x):
        return x

    descriptor = _cachedmethod._wrapper(
        identity,
        cache=lambda self: {},
        key=lambda self, x: x,
    )

    with pytest.raises(TypeError) as exc:
        class Conflict:
            first = descriptor
            second = descriptor  # second assignment should trigger the error

    # Verify that the error mentions the attribute name conflict
    assert "same @cachedmethod" in str(exc.value)
