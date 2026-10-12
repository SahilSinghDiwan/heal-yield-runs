import builtins

import pytest
import cachetools.keys as keys


def test_hashkey_without_kwargs():
    key = keys.hashkey(1, "a")
    # The key should be an instance of the internal _HashedTuple
    assert isinstance(key, keys._HashedTuple)
    # Its tuple representation must match the arguments
    assert tuple(key) == (1, "a")
    # The hash of the key must equal the hash of the underlying tuple
    assert hash(key) == hash((1, "a"))


def test_hashkey_with_kwargs():
    # kwargs are sorted by key name
    key = keys.hashkey(1, b=2, a=3)
    # Expected tuple: args + sentinel + sorted kwargs items
    expected = (1,) + keys._kwmark + (("a", 3), ("b", 2))
    assert isinstance(key, keys._HashedTuple)
    assert tuple(key) == expected
    # The sentinel is the unique class object stored in _kwmark
    assert key[1] is keys._kwmark[0]
    # Hash must match the hash of the underlying tuple
    assert hash(key) == hash(expected)


def test_methodkey_forwards_to_hashkey():
    class Dummy:
        def method(self, *args, **kwargs):
            return keys.methodkey(self, *args, **kwargs)

    d = Dummy()
    key = d.method(10, x=5)
    # methodkey should ignore the bound instance and behave like hashkey
    expected = keys.hashkey(10, x=5)
    assert isinstance(key, keys._HashedTuple)
    assert key == expected


def test_typedkey_without_kwargs():
    key = keys.typedkey(1, "s")
    # Expected: original args followed by their types
    base = (1, "s")
    types = (int, str)
    expected = base + types
    assert isinstance(key, keys._HashedTuple)
    assert tuple(key) == expected
    assert hash(key) == hash(expected)


def test_typedkey_with_kwargs():
    # kwargs are sorted, then types for kw values, then types for args
    key = keys.typedkey(1, a=2, b="x")
    sorted_items = (("a", 2), ("b", "x"))
    base = (1,) + keys._kwmark + sorted_items
    kw_types = (int, str)   # types of 2 and "x"
    arg_types = (int,)      # type of positional arg 1
    expected = base + kw_types + arg_types
    assert isinstance(key, keys._HashedTuple)
    assert tuple(key) == expected
    assert hash(key) == hash(expected)


def test_typedmethodkey_forwards_to_typedkey():
    class C:
        def m(self, *args, **kwargs):
            return keys.typedmethodkey(self, *args, **kwargs)

    c = C()
    key = c.m(3, y=4)
    expected = keys.typedkey(3, y=4)
    assert isinstance(key, keys._HashedTuple)
    assert key == expected


def test_hash_caching_behavior():
    key = keys.hashkey(1, 2, 3)
    # First hash computation
    h1 = hash(key)
    # Subsequent hash calls must return the same cached value
    h2 = hash(key)
    assert h1 == h2
    # The internal cache attribute should now be set to the computed hash
    # Name‑mangling reveals the private attribute on the instance
    cached = getattr(key, "_HashedTuple__hashvalue")
    assert cached == h1
