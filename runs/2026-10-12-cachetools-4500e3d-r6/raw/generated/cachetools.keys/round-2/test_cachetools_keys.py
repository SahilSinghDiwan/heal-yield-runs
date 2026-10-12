import builtins
import types

import pytest
import cachetools.keys as keys


def tuple_contents(htuple):
    """Return a plain tuple representation of a _HashedTuple."""
    return tuple(htuple)


def test_hashkey_without_kwargs():
    key = keys.hashkey(1, 2, "a")
    assert isinstance(key, keys._HashedTuple)
    assert tuple_contents(key) == (1, 2, "a")


def test_hashkey_with_kwargs():
    # kwargs are sorted, and the sentinel _kwmark (a tuple containing the class)
    # appears as the class object itself after concatenation.
    key = keys.hashkey(1, a=2, b=3)
    assert isinstance(key, keys._HashedTuple)
    expected = (1, keys._HashedTuple, ("a", 2), ("b", 3))
    assert tuple_contents(key) == expected


def test_methodkey_forwards_to_hashkey():
    class Dummy:
        def mk(self, *args, **kwargs):
            return keys.methodkey(self, *args, **kwargs)

    d = Dummy()
    # methodkey should ignore the bound instance and behave like hashkey
    key = d.mk(10, x=20)
    expected = (10, keys._HashedTuple, ("x", 20))
    assert isinstance(key, keys._HashedTuple)
    assert tuple_contents(key) == expected


def test_typedkey_without_kwargs():
    key = keys.typedkey(1, "x")
    assert isinstance(key, keys._HashedTuple)
    # args followed by their types
    expected = (1, "x", int, str)
    assert tuple_contents(key) == expected


def test_typedkey_with_kwargs():
    # Unsorted kwargs to verify sorting.
    key = keys.typedkey(1, b="x", a=2)
    assert isinstance(key, keys._HashedTuple)
    # Sorted kwargs: ('a', 2), ('b', 'x')
    # Sentinel appears as the class object.
    expected = (
        1,
        keys._HashedTuple,
        ("a", 2),
        ("b", "x"),
        int,   # type of positional arg 1
        int,   # type of kwarg value 2
        str,   # type of kwarg value "x"
    )
    assert tuple_contents(key) == expected


def test_typedmethodkey_forwards_to_typedkey():
    class Dummy:
        def mk(self, *args, **kwargs):
            return keys.typedmethodkey(self, *args, **kwargs)

    d = Dummy()
    key = d.mk(5, y="z")
    expected = (
        5,
        keys._HashedTuple,
        ("y", "z"),
        int,   # type of positional arg
        str,   # type of kwarg value
    )
    assert isinstance(key, keys._HashedTuple)
    assert tuple_contents(key) == expected


def test_hash_caching_behavior():
    key = keys.hashkey(1, 2, a=3)
    # Before hashing, the mangled attribute should not exist or be None.
    mangled_name = "_HashedTuple__hashvalue"
    assert not hasattr(key, mangled_name) or getattr(key, mangled_name) is None

    first_hash = hash(key)
    # After first hash, the cached value should be stored.
    assert hasattr(key, mangled_name)
    cached = getattr(key, mangled_name)
    assert cached == first_hash

    # Subsequent hashes should return the same value without recomputation.
    second_hash = hash(key)
    assert second_hash == first_hash
