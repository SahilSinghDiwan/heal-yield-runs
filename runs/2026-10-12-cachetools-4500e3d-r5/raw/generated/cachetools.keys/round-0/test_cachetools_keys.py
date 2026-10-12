import builtins
import types

import pytest

import cachetools.keys as keys


def test_hashkey_without_kwargs():
    # Simple positional arguments
    k = keys.hashkey(1, "a", (2, 3))
    assert isinstance(k, keys._HashedTuple)
    # The tuple content should match the arguments exactly
    assert tuple(k) == (1, "a", (2, 3))
    # Hash should be stable and computed only once (second call returns same value)
    h1 = hash(k)
    h2 = hash(k)
    assert h1 == h2


def test_hashkey_with_kwargs_and_ordering():
    # kwargs are sorted by key name
    k = keys.hashkey(10, b=2, a=1)
    # Expected order: positional args, sentinel, sorted kwargs items
    expected = (10, ) + keys._kwmark + (("a", 1), ("b", 2))
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == expected
    # Ensure the sentinel is the class object, not an instance
    assert k[1] is keys._HashedTuple
    # Hash stability
    assert hash(k) == hash(k)


def test_methodkey_ignores_self():
    class Dummy:
        pass

    dummy = Dummy()
    # methodkey should ignore the first argument (self) and behave like hashkey
    k1 = keys.methodkey(dummy, 5, x=9)
    k2 = keys.hashkey(5, x=9)
    assert k1 == k2
    assert isinstance(k1, keys._HashedTuple)


def test_typedkey_positional_only():
    k = keys.typedkey(1, "s", 3.14)
    # Should contain original args followed by their types
    expected = (1, "s", 3.14) + (int, str, float)
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == expected
    # Hash stability
    assert hash(k) == hash(k)


def test_typedkey_with_kwargs():
    # Mix positional and keyword arguments
    k = keys.typedkey(1, y="yval", x=2)
    # kwargs are sorted by key name: ('x', 2), ('y', 'yval')
    sorted_kwargs = (("x", 2), ("y", "yval"))
    # Types for kwargs values then types for positional args
    expected = (1,) + keys._kwmark + sorted_kwargs + (int, str) + (int,)
    # Explanation:
    #   args: (1,)
    #   sentinel
    #   sorted kwargs items
    #   types of kw values (int for 2, str for "yval")
    #   types of positional args (int for 1)
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == expected
    # Ensure the sentinel is present exactly once
    assert tuple(k).count(keys._HashedTuple) == 1
    # Hash stability
    assert hash(k) == hash(k)


def test_typedmethodkey_delegates_to_typedkey():
    class Foo:
        pass

    foo = Foo()
    k1 = keys.typedmethodkey(foo, "a", b=2)
    k2 = keys.typedkey("a", b=2)
    assert k1 == k2
    assert isinstance(k1, keys._HashedTuple)


def test_hashedtuple_addition_and_raddition():
    a = keys._HashedTuple((1, 2))
    b = keys._HashedTuple((3,))
    # a + b returns a new _HashedTuple
    c = a + b
    assert isinstance(c, keys._HashedTuple)
    assert tuple(c) == (1, 2, 3)
    # b + a via __radd__
    d = b.__radd__(a)
    assert isinstance(d, keys._HashedTuple)
    assert tuple(d) == (1, 2, 3)
    # Ensure hash stability after addition
    assert hash(c) == hash(c)
    assert hash(d) == hash(d)


def test_hashedtuple_getstate_returns_empty_dict():
    ht = keys._HashedTuple((42,))
    state = ht.__getstate__()
    assert isinstance(state, dict)
    assert state == {}
