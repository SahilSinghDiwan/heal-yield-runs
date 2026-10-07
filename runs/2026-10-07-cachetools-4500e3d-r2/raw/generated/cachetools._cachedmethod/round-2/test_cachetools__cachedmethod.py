import threading
import warnings

import pytest

import cachetools._cachedmethod as cm


def simple_cache():
    """Factory returning a fresh dict cache."""
    return {}


def simple_key(self, *args, **kwargs):
    """Key function that uses the first positional argument (or None)."""
    return args[0] if args else None


def simple_info(cache, hits, misses):
    """Info function returning a tuple of hits and misses."""
    return hits, misses


# ----------------------------------------------------------------------
# Helper to create a descriptor using the internal _wrapper function.
def make_descriptor(method, cache_func, key_func, *, lock=None, cond=None, info=None):
    """Create a cachedmethod descriptor using the private _wrapper."""
    return cm._wrapper(
        method,
        cache=cache_func,
        key=key_func,
        lock=lock,
        cond=cond,
        info=info,
    )


# ----------------------------------------------------------------------
# Tests that were already passing (kept unchanged in spirit)

def test_unlocked_caches_and_counts():
    class Foo:
        def __init__(self):
            self._cache = {}

        @make_descriptor
        def inc(self, x):
            return x + 1

    # Build the descriptor manually to avoid reliance on the decorator syntax
    def inc(self, x):
        return x + 1

    Foo.inc = make_descriptor(
        inc,
        cache=lambda self: self._cache,
        key=simple_key,
        info=simple_info,
    )

    f = Foo()
    # first call – miss
    assert f.inc(10) == 11
    # second call – hit
    assert f.inc(10) == 11
    # different argument – miss
    assert f.inc(20) == 21

    # cache should contain two entries
    assert set(f._cache.keys()) == {10, 20}
    # cache_info should report 1 hit, 2 misses
    assert f.inc.cache_info() == (1, 2)

    # clear cache and counters
    f.inc.cache_clear()
    assert f._cache == {}
    assert f.inc.cache_info() == (0, 0)


def test_locked_caches_and_counts():
    lock = threading.Lock()

    class Bar:
        def __init__(self):
            self._cache = {}

        @make_descriptor
        def mul(self, x):
            return x * 2

    def mul(self, x):
        return x * 2

    Bar.mul = make_descriptor(
        mul,
        cache=lambda self: self._cache,
        key=simple_key,
        lock=lambda self: lock,
        info=simple_info,
    )

    b = Bar()
    # first call – miss
    assert b.mul(3) == 6
    # second call – hit
    assert b.mul(3) == 6
    # different argument – miss
    assert b.mul(4) == 8

    assert set(b._cache.keys()) == {3, 4}
    assert b.mul.cache_info() == (1, 2)

    b.mul.cache_clear()
    assert b._cache == {}
    assert b.mul.cache_info() == (0, 0)


def test_conditioned_caches_and_counts():
    lock = threading.Lock()
    cond = threading.Condition(lock)

    class Baz:
        def __init__(self):
            self._cache = {}

        @make_descriptor
        def add(self, x, y):
            return x + y

    def add(self, x, y):
        return x + y

    Baz.add = make_descriptor(
        add,
        cache=lambda self: self._cache,
        key=lambda self, x, y: (x, y),
        lock=lambda self: lock,
        cond=lambda self: cond,
        info=simple_info,
    )

    z = Baz()
    # first call – miss
    assert z.add(1, 2) == 3
    # second call – hit
    assert z.add(1, 2) == 3
    # different args – miss
    assert z.add(2, 3) == 5

    assert set(z._cache.keys()) == {(1, 2), (2, 3)}
    assert z.add.cache_info() == (1, 2)

    z.add.cache_clear()
    assert z._cache == {}
    assert z.add.cache_info() == (0, 0)


# ----------------------------------------------------------------------
# Additional tests to cover edge‑cases and previously failing behaviour

def test_descriptor_set_name_error():
    """Assigning the same descriptor instance to two different names should raise."""
    class Dummy:
        pass

    # Create a descriptor manually
    def method(self):
        return 42

    descriptor = make_descriptor(
        method,
        cache=lambda self: {},
        key=lambda self: None,
    )

    # First assignment works
    Dummy.first = descriptor
    # Second assignment with a different name must raise TypeError
    with pytest.raises(TypeError) as exc:
        Dummy.second = descriptor
    assert "Cannot assign the same @cachedmethod to two different names" in str(exc.value)


def test_no_dict_raises_typeerror():
    """Objects without a __dict__ (e.g., slots) should raise TypeError when caching."""
    class NoDict:
        __slots__ = ()

        def __init__(self):
            self._cache = {}

    def method(self, x):
        return x

    descriptor = make_descriptor(
        method,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
    )
    NoDict.cached = descriptor

    obj = NoDict()
    # Accessing the cached method should raise TypeError because __dict__ is missing
    with pytest.raises(TypeError) as exc:
        obj.cached(1)
    assert "No '__dict__' attribute on 'NoDict' instance" in str(exc.value)


def test_deprecated_classmethod_warning():
    """Using a cachedmethod as a classmethod should emit a DeprecationWarning."""
    lock = threading.Lock()
    cond = threading.Condition(lock)

    class C:
        _cache = {}

        @make_descriptor
        def cls_method(cls, x):
            return x * 10

    # Build a descriptor that mimics the deprecated classmethod path
    def method(cls, x):
        return x * 10

    descriptor = cm._condition(
        method,
        cache=lambda self: C._cache,
        key=lambda self, x: x,
        lock=lambda self: lock,
        cond=lambda self: cond,
    )
    C.cls = descriptor

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Calling via the class should trigger the deprecation warning
        result = C.cls(5)
        assert result == 50
        # At least one warning should have been captured
        assert any(issubclass(wi.category, DeprecationWarning) for wi in w)
        # The warning message should mention the deprecation of class methods
        assert any("decorating class methods with @cachedmethod is deprecated" in str(wi.message) for wi in w)


def test_class_access_returns_wrapper():
    """Accessing the descriptor through the class should return a wrapper object."""
    class D:
        def __init__(self):
            self._cache = {}

        @make_descriptor
        def foo(self, x):
            return x + 5

    def foo(self, x):
        return x + 5

    D.foo = make_descriptor(
        foo,
        cache=lambda self: self._cache,
        key=lambda self, x: x,
    )

    # Access via class returns a wrapper (not the original function)
    wrapper = D.foo
    # The wrapper should have the expected attributes
    assert hasattr(wrapper, "cache")
    assert hasattr(wrapper, "cache_key")
    assert hasattr(wrapper, "cache_lock")
    assert hasattr(wrapper, "cache_condition")
    # Calling the wrapper directly with an instance should work
    d = D()
    assert wrapper(d, 2) == 7
