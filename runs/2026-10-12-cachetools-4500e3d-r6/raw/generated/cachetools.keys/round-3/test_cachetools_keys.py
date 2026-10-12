import builtins

import pytest

# Import the module under test using its dotted path.
from cachetools import keys


def tuple_contents(hashed_tuple):
    """Utility to convert a _HashedTuple into a plain tuple for inspection."""
    return tuple(hashed_tuple)


def test_hashkey_without_kwargs():
    key = keys.hashkey(1, 2, "three")
    assert isinstance(key, keys._HashedTuple)
    # No kwargs: the key should be exactly the arguments as a tuple.
    assert tuple_contents(key) == (1, 2, "three")


def test_hashkey_with_kwargs():
    # Unsorted kwargs to verify sorting.
    key = keys.hashkey(1, b="x", a=2)
    assert isinstance(key, keys._HashedTuple)
    # Sorted kwargs: ('a', 2), ('b', 'x')
    # The sentinel appears as the class object.
    expected = (
        1,
        keys._HashedTuple,  # sentinel separating args from kwargs
        ("a", 2),
        ("b", "x"),
    )
    assert tuple_contents(key) == expected


def test_methodkey_forwards_to_hashkey():
    class Dummy:
        def mk(self, *args, **kwargs):
            return keys.methodkey(*args, **kwargs)

    d = Dummy()
    # methodkey should behave exactly like hashkey.
    assert tuple_contents(d.mk(1, a=2)) == tuple_contents(keys.hashkey(1, a=2))


def test_typedkey_without_kwargs():
    key = keys.typedkey(1, "x")
    assert isinstance(key, keys._HashedTuple)
    # No kwargs: args followed by their types.
    expected = (1, "x", int, str)
    assert tuple_contents(key) == expected


def test_typedkey_with_kwargs():
    # Unsorted kwargs to verify sorting.
    key = keys.typedkey(1, b="x", a=2)
    assert isinstance(key, keys._HashedTuple)

    # The structure is:
    # (positional args..., sentinel, sorted kwargs..., types of kwargs..., types of args...)
    # Sorted kwargs: ('a', 2), ('b', 'x')
    # Types for kwargs (in sorted order): int, str
    # Types for positional args: int
    expected_prefix = (
        1,
        keys._HashedTuple,  # sentinel
        ("a", 2),
        ("b", "x"),
    )
    # Verify the prefix matches.
    assert tuple_contents(key)[:4] == expected_prefix

    # Verify the trailing type entries are in the order produced by the implementation:
    # kwarg types first, then positional arg types.
    expected_suffix = (int, str, int)
    assert tuple_contents(key)[4:] == expected_suffix


def test_typedmethodkey_forwards_to_typedkey():
    class Dummy:
        def mk(self, *args, **kwargs):
            return keys.typedmethodkey(self, *args, **kwargs)

    d = Dummy()
    key = d.mk(5, y="z")
    assert isinstance(key, keys._HashedTuple)

    # Expected structure:
    # (positional args..., sentinel, sorted kwargs..., kwarg types..., positional arg types...)
    expected_prefix = (
        5,
        keys._HashedTuple,  # sentinel
        ("y", "z"),
    )
    assert tuple_contents(key)[:3] == expected_prefix

    # Types: kwarg type (str) first, then positional arg type (int)
    expected_suffix = (str, int)
    assert tuple_contents(key)[3:] == expected_suffix


def test_hash_caching_behavior():
    # Ensure that hashing a _HashedTuple does not change across calls.
    key = keys.hashkey(1, a=2)
    first_hash = hash(key)
    second_hash = hash(key)
    assert first_hash == second_hash
    # Also verify that the hash value is an int.
    assert isinstance(first_hash, int)
