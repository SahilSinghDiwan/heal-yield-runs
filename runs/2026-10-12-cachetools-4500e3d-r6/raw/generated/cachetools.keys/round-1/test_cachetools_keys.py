import builtins
import types

import pytest

# Import the module under test using its full dotted path.
from cachetools import keys


# ---------------------------------------------------------------------------
# Helper to compare the internal representation of a _HashedTuple.
# ---------------------------------------------------------------------------
def tuple_contents(hashed_tuple):
    """Return a plain tuple with the same contents as a _HashedTuple."""
    # _HashedTuple is a subclass of tuple, so converting to tuple works.
    return tuple(hashed_tuple)


# ---------------------------------------------------------------------------
# Tests for hashkey
# ---------------------------------------------------------------------------
def test_hashkey_without_kwargs():
    key = keys.hashkey(1, "a")
    # Should be an instance of the internal _HashedTuple subclass.
    assert isinstance(key, keys._HashedTuple)
    # No sentinel should be present when there are no kwargs.
    assert tuple_contents(key) == (1, "a")


def test_hashkey_with_kwargs():
    key = keys.hashkey(1, a=2, b=3)
    # The sentinel _kwmark should separate positional args from sorted kwargs.
    expected = (1, keys._kwmark, ("a", 2), ("b", 3))
    assert isinstance(key, keys._HashedTuple)
    assert tuple_contents(key) == expected


def test_methodkey_forwards_to_hashkey():
    class Dummy:
        pass

    dummy = Dummy()
    # methodkey should ignore the bound instance and behave like hashkey.
    key1 = keys.methodkey(dummy, 10, foo="bar")
    key2 = keys.hashkey(10, foo="bar")
    assert isinstance(key1, keys._HashedTuple)
    assert key1 == key2


# ---------------------------------------------------------------------------
# Tests for typedkey
# ---------------------------------------------------------------------------
def test_typedkey_without_kwargs():
    key = keys.typedkey(1, "a")
    # Expected layout: positional values followed by their types.
    expected = (1, "a", int, str)
    assert isinstance(key, keys._HashedTuple)
    assert tuple_contents(key) == expected


def test_typedkey_with_kwargs():
    # Use unsorted kwargs to verify that sorting occurs.
    key = keys.typedkey(1, b="x", a=2)
    # Sorted kwargs items: ('a', 2), ('b', 'x')
    expected = (
        1,
        keys._kwmark,
        ("a", 2),
        ("b", "x"),
        int,          # type of positional arg 1
        int,          # type of kwarg value 2
        str,          # type of kwarg value "x"
    )
    assert isinstance(key, keys._HashedTuple)
    assert tuple_contents(key) == expected


def test_typedmethodkey_forwards_to_typedkey():
    class Dummy:
        pass

    dummy = Dummy()
    key1 = keys.typedmethodkey(dummy, 5, flag=True)
    key2 = keys.typedkey(5, flag=True)
    assert isinstance(key1, keys._HashedTuple)
    assert key1 == key2


# ---------------------------------------------------------------------------
# Test that the hash of a _HashedTuple is cached after the first call.
# ---------------------------------------------------------------------------
def test_hash_caching_behavior():
    key = keys.hashkey(1, 2, 3)
    # Ensure the internal cache attribute is initially None.
    assert getattr(key, "_HashedTuple__hashvalue") is None

    # First hash computation should set the cached value.
    first_hash = hash(key)
    cached = getattr(key, "_HashedTuple__hashvalue")
    assert cached == first_hash

    # Subsequent hash calls should return the same cached value without recomputing.
    for _ in range(5):
        assert hash(key) == cached
