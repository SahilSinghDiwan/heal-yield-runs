import builtins
import types

import pytest

# Import the module under test
from cachetools import keys


class CounterHash:
    """Object whose __hash__ increments an external counter."""
    def __init__(self, counter):
        self._counter = counter

    def __hash__(self):
        self._counter["calls"] += 1
        # Return a constant hash value to keep tuple hash stable
        return 42


def test_hashkey_simple_args():
    # No kwargs: should return a _HashedTuple containing the args only
    key = keys.hashkey(1, "a", (2, 3))
    assert isinstance(key, keys._HashedTuple)
    assert tuple(key) == (1, "a", (2, 3))


def test_hashkey_with_kwargs_and_sorting():
    # Kwargs should be sorted by key name and separated by the sentinel
    key = keys.hashkey(10, b=2, a=1)
    # The sentinel is the first element of the internal _kwmark tuple
    sentinel = keys._kwmark[0]
    # Expected tuple layout
    expected = (10, sentinel, ("a", 1), ("b", 2))
    assert isinstance(key, keys._HashedTuple)
    assert tuple(key) == expected


def test_hashkey_hash_caching():
    # Verify that hashing the key only triggers element __hash__ once
    counter = {"calls": 0}
    obj = CounterHash(counter)
    key = keys.hashkey(obj, 5)

    # First hash: element __hash__ should be called
    h1 = hash(key)
    assert counter["calls"] == 1

    # Second hash: element __hash__ should NOT be called again
    h2 = hash(key)
    assert counter["calls"] == 1
    assert h1 == h2


def test_methodkey_ignores_self():
    class Dummy:
        pass

    dummy = Dummy()
    # methodkey should behave exactly like hashkey for the remaining args
    key1 = keys.methodkey(dummy, 1, x=2)
    key2 = keys.hashkey(1, x=2)
    assert key1 == key2
    assert isinstance(key1, keys._HashedTuple)


def test_typedkey_without_kwargs():
    # Types of positional arguments are appended after the args
    key = keys.typedkey(10, "s")
    # Expected: (10, "s", int, str)
    assert isinstance(key, keys._HashedTuple)
    assert tuple(key) == (10, "s", int, str)


def test_typedkey_with_kwargs():
    # Types for kwargs values are added before types for positional args
    key = keys.typedkey(1, a="foo", b=3.14)
    sentinel = keys._kwmark[0]
    # Sorted kwargs: a then b
    expected = (
        1,
        sentinel,
        ("a", "foo"),
        ("b", 3.14),
        str,          # type of kwarg "foo"
        float,        # type of kwarg 3.14
        int,          # type of positional arg 1
    )
    assert isinstance(key, keys._HashedTuple)
    assert tuple(key) == expected


def test_typedmethodkey_behaviour():
    class C:
        pass

    c = C()
    # typedmethodkey should be identical to typedkey for the same args/kwargs
    key1 = keys.typedmethodkey(c, 7, flag=True)
    key2 = keys.typedkey(7, flag=True)
    assert key1 == key2
    assert isinstance(key1, keys._HashedTuple)


def test_empty_calls_return_empty_hashedtuple():
    # No args, no kwargs
    assert isinstance(keys.hashkey(), keys._HashedTuple)
    assert tuple(keys.hashkey()) == ()

    assert isinstance(keys.typedkey(), keys._HashedTuple)
    assert tuple(keys.typedkey()) == ()


def test_hashedtuple_addition_preserves_type():
    # Ensure that __add__ and __radd__ produce another _HashedTuple
    base = keys._HashedTuple((1, 2))
    added = base + (3,)
    radded = (0,) + base
    assert isinstance(added, keys._HashedTuple)
    assert isinstance(radded, keys._HashedTuple)
    assert tuple(added) == (1, 2, 3)
    assert tuple(radded) == (0, 1, 2)
