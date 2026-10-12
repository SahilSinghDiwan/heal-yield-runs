import builtins
import types

import pytest
from cachetools import keys


def test_hashkey_positional_only():
    # Simple positional arguments
    k = keys.hashkey(1, "a", (2, 3))
    # Should be an instance of the internal _HashedTuple
    assert isinstance(k, keys._HashedTuple)
    # The underlying tuple should match the args
    assert tuple(k) == (1, "a", (2, 3))
    # Hash should be computed and cached
    first_hash = hash(k)
    # Access the mangled attribute that stores the cached hash value
    cached = k._HashedTuple__hashvalue
    assert cached == first_hash
    # Subsequent hash calls return the same value without recomputation
    assert hash(k) == cached


def test_hashkey_with_kwargs_and_ordering():
    # Provide kwargs in unsorted order
    k = keys.hashkey(10, b=2, a=1)
    # Expected tuple: args + kwmark sentinel + sorted kw items
    expected = (10,) + keys._kwmark + (("a", 1), ("b", 2))
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == expected
    # Ensure the sentinel is the exact object defined in the module
    assert k[1] is keys._kwmark[0]
    # Changing order of kwargs should not affect the key
    k2 = keys.hashkey(10, a=1, b=2)
    assert k == k2
    # Hashes should be equal
    assert hash(k) == hash(k2)


def test_methodkey_ignores_self():
    class Dummy:
        def __init__(self, val):
            self.val = val

        def key(self, *args, **kwargs):
            return keys.methodkey(self, *args, **kwargs)

    d = Dummy(5)
    # methodkey should behave like hashkey on the arguments only
    expected = keys.hashkey(1, 2, x=3)
    result = d.key(1, 2, x=3)
    assert result == expected
    # Ensure the result is still a _HashedTuple
    assert isinstance(result, keys._HashedTuple)


def test_typedkey_positional_only():
    k = keys.typedkey(1, "a")
    # Underlying tuple: args + types of args
    expected = (1, "a") + (int, str)
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == expected
    # Types are correctly appended
    assert k[-2:] == (int, str)


def test_typedkey_with_kwargs():
    # Provide kwargs out of order to test sorting
    k = keys.typedkey(1, a=2, b="x")
    # Build expected step by step
    sorted_kwargs = (("a", 2), ("b", "x"))
    # args + kwmark + sorted kwargs
    base = (1,) + keys._kwmark + sorted_kwargs
    # Append types of kw values then types of args
    expected = base + (int, str) + (int,)
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == expected
    # Ensure the kwmark sentinel is correctly placed
    assert k[1] is keys._kwmark[0]
    # Types order: first kwargs values, then positional args
    assert tuple(k[-3:]) == (int, int, int)[:3]  # sanity check length


def test_typedmethodkey_forwards_to_typedkey():
    class Foo:
        def __init__(self, x):
            self.x = x

        def cache_key(self, *args, **kwargs):
            return keys.typedmethodkey(self, *args, **kwargs)

    f = Foo(10)
    # Should be identical to typedkey on the same args/kwargs
    expected = keys.typedkey(1, a=2)
    result = f.cache_key(1, a=2)
    assert result == expected
    assert isinstance(result, keys._HashedTuple)


def test_hash_consistency_across_calls():
    # Same arguments should produce equal keys and equal hashes
    k1 = keys.hashkey(1, 2, a=3)
    k2 = keys.hashkey(1, 2, a=3)
    assert k1 == k2
    assert hash(k1) == hash(k2)

    # Different arguments should not be equal
    k3 = keys.hashkey(1, 2, a=4)
    assert k1 != k3
    assert hash(k1) != hash(k3)


def test_empty_arguments():
    # No args, no kwargs
    k = keys.hashkey()
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == ()
    # Typed version adds no types
    tk = keys.typedkey()
    assert isinstance(tk, keys._HashedTuple)
    assert tuple(tk) == ()
