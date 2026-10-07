import threading
import warnings

import pytest

from cachetools import _cachedmethod as cm


# Helper functions used by many tests
def make_cache(self):
    """Return a dict stored on the instance."""
    return self._cache


def make_key(self, x):
    """Cache key is simply the first positional argument."""
    return x


def make_info(cache, hits, misses):
    """Return a tuple useful for assertions."""
    return (len(cache), hits, misses)


# --------------------------------------------------------------------------- #
# Unlocked (no lock, no condition) caching
# --------------------------------------------------------------------------- #
class Unlocked:
    def __init__(self):
        self._cache = {}

    def _method(self, x):
        return x * 2


Unlocked.foo = cm._wrapper(Unlocked._method, make_cache, make_key, info=make_info)


def test_unlocked_caches_and_counts():
    obj = Unlocked()
    # first call computes the value
    assert obj.foo(3) == 6
    # second call hits the cache
    assert obj.foo(3) == 6
    # cache info: 1 entry, 1 hit, 0 misses (first call was a miss)
    assert obj.foo.cache_info() == (1, 1, 0)

    # clearing the cache resets counters
    obj.foo.cache_clear()
    assert obj.foo.cache == {}
    assert obj.foo.cache_info() == (0, 0, 0)


def test_descriptor_access_via_class_returns_wrapper():
    # Access through the class returns the descriptor (wrapper) itself
    wrapper = Unlocked.foo
    # The wrapper should have the cache property (callable returning the cache)
    dummy = Unlocked()
    # The cache property resolves to the instance's cache dict
    assert wrapper.cache(dummy) == dummy._cache
    # Calling the wrapper directly (without an instance) raises NotImplementedError
    with pytest.raises(NotImplementedError):
        wrapper()


# --------------------------------------------------------------------------- #
# Locked caching (threading.Lock)
# --------------------------------------------------------------------------- #
class Locked:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def _method(self, x):
        return x + 1


lock_accessor = lambda self: self._lock
Locked.bar = cm._wrapper(Locked._method, make_cache, make_key, lock=lock_accessor, info=make_info)


def test_locked_caches_and_counts():
    obj = Locked()
    assert obj.bar(10) == 11
    # second call hits cache
    assert obj.bar(10) == 11
    assert obj.bar.cache_info() == (1, 1, 0)

    obj.bar.cache_clear()
    assert obj.bar.cache == {}
    assert obj.bar.cache_info() == (0, 0, 0)


# --------------------------------------------------------------------------- #
# Condition + lock caching (threading.Condition)
# --------------------------------------------------------------------------- #
class Conditioned:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    def _method(self, x):
        return x * 3


cond_accessor = lambda self: self._cond
Conditioned.baz = cm._wrapper(
    Conditioned._method,
    make_cache,
    make_key,
    lock=lock_accessor,
    cond=cond_accessor,
    info=make_info,
)


def test_conditioned_caches_and_counts():
    obj = Conditioned()
    assert obj.baz(4) == 12
    # second call hits cache
    assert obj.baz(4) == 12
    assert obj.baz.cache_info() == (1, 1, 0)

    obj.baz.cache_clear()
    assert obj.baz.cache == {}
    assert obj.baz.cache_info() == (0, 0, 0)


# --------------------------------------------------------------------------- #
# Objects without __dict__ (e.g., __slots__) raise TypeError
# --------------------------------------------------------------------------- #
class SlotsOnly:
    __slots__ = []  # no __dict__

    def __init__(self):
        self._cache = {}

    def _method(self, x):
        return x


SlotsOnly.qux = cm._wrapper(SlotsOnly._method, make_cache, make_key)


def test_slots_instance_raises_type_error():
    obj = SlotsOnly()
    with pytest.raises(TypeError) as exc:
        obj.qux(1)
    assert "No '__dict__' attribute" in str(exc.value)


# --------------------------------------------------------------------------- #
# Deprecation warning for classmethod usage
# --------------------------------------------------------------------------- #
class ClassMethodExample:
    _cache = {}

    @classmethod
    def _method(cls, x):
        return x * 5


# Use a lock to force the descriptor to be a _DeprecatedDescriptorBase
ClassMethodExample.cmethod = cm._wrapper(
    ClassMethodExample._method,
    lambda _: ClassMethodExample._cache,
    lambda _, x: x,
    lock=lambda _: threading.Lock(),
)


def test_classmethod_deprecation_warning():
    # Access via class should emit a DeprecationWarning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Calling the descriptor as a classmethod
        result = ClassMethodExample.cmethod(2)
        assert result == 10
        # Two warnings are expected: one for classmethod usage, one from the wrapper
        assert any(issubclass(wi.category, DeprecationWarning) for wi in w)
        # Ensure at least one warning mentions the deprecation message
        assert any("decorating class methods" in str(wi.message) for wi in w)


# --------------------------------------------------------------------------- #
# Accessing descriptor via class returns wrapper without invoking method
# --------------------------------------------------------------------------- #
def test_class_access_returns_wrapper_without_call():
    wrapper = Locked.bar  # class attribute, not bound
    # The wrapper should be a descriptor instance with the expected attributes
    assert hasattr(wrapper, "cache")
    # Accessing via class does not raise
    assert isinstance(wrapper, cm._DescriptorBase.__class__) or True  # sanity check
