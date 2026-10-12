import builtins
import types

import pytest

# Import the module under test using its dotted path
import cachetools.keys as keys


def test_hashkey_without_kwargs_returns_hashedtuple_and_preserves_order():
    key = keys.hashkey(1, "a", (2, 3))
    # The result should be an instance of the internal _HashedTuple
    assert isinstance(key, keys._HashedTuple)
    # The contents should match the input arguments in order
    assert tuple(key) == (1, "a", (2, 3))


def test_hashkey_with_kwargs_includes_kwmark_and_sorted_items():
    key = keys.hashkey(1, b=2, a=3)
    # Should be a _HashedTuple
    assert isinstance(key, keys._HashedTuple)
    # The sentinel should be present exactly once and be the same object as _kwmark[0]
    sentinel = keys._kwmark[0]
    # Find sentinel position
    assert sentinel in key
    # Build expected tuple manually
    expected = (1,) + keys._kwmark + (("a", 3), ("b", 2))
    assert tuple(key) == expected


def test_hashkey_hash_is_cached_and_consistent():
    key = keys.hashkey("x", y=5)
    # Compute hash twice; both should be equal
    first_hash = hash(key)
    second_hash = hash(key)
    assert first_hash == second_hash
    # Ensure that the cached hash value is stored on the instance
    # (accessing the private attribute directly for verification)
    assert getattr(key, "_HashedTuple__hashvalue") == first_hash


def test_methodkey_ignores_self_and_matches_hashkey():
    class Dummy:
        pass

    dummy1 = Dummy()
    dummy2 = Dummy()
    # methodkey should ignore the self argument and behave like hashkey
    key1 = keys.methodkey(dummy1, 10, foo="bar")
    key2 = keys.methodkey(dummy2, 10, foo="bar")
    expected = keys.hashkey(10, foo="bar")
    assert key1 == expected
    assert key2 == expected
    # Different self should not affect the key
    assert key1 == key2


def test_typedkey_without_kwargs_appends_type_information():
    key = keys.typedkey(42, "hello")
    # Should be a _HashedTuple
    assert isinstance(key, keys._HashedTuple)
    # Expected content: original args followed by their types
    expected = (42, "hello", int, str)
    assert tuple(key) == expected


def test_typedkey_with_kwargs_includes_kwmark_and_type_info():
    key = keys.typedkey(1, b=2, a="z")
    # Should be a _HashedTuple
    assert isinstance(key, keys._HashedTuple)

    # Build expected tuple step by step
    # Sorted kwargs: ('a', 'z'), ('b', 2)
    sorted_kwargs = (("a", "z"), ("b", 2))
    sentinel = keys._kwmark
    # Types for kwargs values
    kw_types = (type("z"), type(2))
    # Types for positional args
    arg_types = (type(1),)

    expected = (1,) + sentinel + sorted_kwargs + kw_types + arg_types
    assert tuple(key) == expected


def test_typedmethodkey_forwards_to_typedkey():
    class Dummy:
        pass

    dummy = Dummy()
    # typedmethodkey should produce the same result as typedkey
    result = keys.typedmethodkey(dummy, 3, flag=True)
    expected = keys.typedkey(3, flag=True)
    assert result == expected
    # Ensure the result is a _HashedTuple
    assert isinstance(result, keys._HashedTuple)


def test_hashkey_is_immutable_against_original_mutable_arguments():
    mutable = [1, 2]
    key = keys.hashkey(mutable)
    # Mutate the original list after key creation
    mutable.append(3)
    # The key should retain the original content (the list object itself is stored,
    # but its hash depends on its current state; however, hashkey does not copy,
    # so we check that the tuple element is the same object)
    assert key[0] is mutable
    # The hash of the key should now reflect the mutated list
    # (this demonstrates that hashkey does not deep‑copy arguments)
    assert hash(key) == hash(keys._HashedTuple((mutable,)))


def test_addition_of_hashedtuple_returns_hashedtuple():
    base = keys.hashkey(1, 2)
    added = base + (3,)
    # The result of addition should be a _HashedTuple, not a plain tuple
    assert isinstance(added, keys._HashedTuple)
    # Content should be concatenated correctly
    assert tuple(added) == (1, 2, 3)

    # Also test right‑addition
    added_r = (0,) + base
    assert isinstance(added_r, keys._HashedTuple)
    assert tuple(added_r) == (0, 1, 2)
