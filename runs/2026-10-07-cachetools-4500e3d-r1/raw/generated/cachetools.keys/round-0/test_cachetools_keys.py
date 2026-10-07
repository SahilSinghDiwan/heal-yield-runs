import builtins

import pytest

import cachetools.keys as keys


def test_hashkey_without_kwargs_hash_caching():
    # Simple key with positional arguments only
    key = keys.hashkey(1, "a", (2, 3))
    assert isinstance(key, keys._HashedTuple)
    # The tuple content should match the arguments
    assert tuple(key) == (1, "a", (2, 3))

    # Before hashing, the internal cache is empty
    assert getattr(key, "_HashedTuple__hashvalue") is None

    # First hash computes and stores the value
    first_hash = hash(key)
    cached = getattr(key, "_HashedTuple__hashvalue")
    assert cached == first_hash

    # Subsequent hashes return the cached value without recomputation
    second_hash = hash(key)
    assert second_hash == first_hash
    assert getattr(key, "_HashedTuple__hashvalue") == first_hash


def test_hashkey_with_kwargs_order_and_sentinel():
    # kwargs order should not affect the resulting key
    key1 = keys.hashkey(1, b=2, a=3)
    key2 = keys.hashkey(1, a=3, b=2)
    assert key1 == key2
    assert isinstance(key1, keys._HashedTuple)

    # The sentinel should be present exactly once and preserve identity
    sentinel = keys._kwmark
    assert key1[1] is sentinel

    # The sorted kwargs should appear after the sentinel
    expected_kwargs = (("a", 3), ("b", 2))
    assert tuple(key1[2:]) == expected_kwargs


def test_methodkey_ignores_self():
    class Dummy:
        pass

    dummy = Dummy()
    # methodkey receives the instance as the first argument but discards it
    key_via_method = keys.methodkey(dummy, 10, flag=True)
    key_direct = keys.hashkey(10, flag=True)
    assert key_via_method == key_direct
    assert isinstance(key_via_method, keys._HashedTuple)


def test_typedkey_without_kwargs():
    key = keys.typedkey(10, "test")
    # Base arguments
    assert tuple(key[:2]) == (10, "test")
    # Types appended for each positional argument (int, str)
    assert tuple(key[2:]) == (int, str)
    assert isinstance(key, keys._HashedTuple)


def test_typedkey_with_kwargs_and_type_order():
    # Mixed positional and keyword arguments
    key = keys.typedkey(1, a="x", b=2)

    # Expected structure:
    # (positional args) + sentinel + sorted kwargs + types of kwargs values + types of positional args
    sentinel = keys._kwmark
    sorted_kwargs = (("a", "x"), ("b", 2))
    expected_base = (1, sentinel) + sorted_kwargs
    expected_types_kwargs = (str, int)  # types of "x" and 2
    expected_types_args = (int,)        # type of 1

    # Verify the tuple content step by step
    assert tuple(key[: len(expected_base)]) == expected_base
    offset = len(expected_base)
    assert tuple(key[offset : offset + len(expected_types_kwargs)]) == expected_types_kwargs
    offset += len(expected_types_kwargs)
    assert tuple(key[offset:]) == expected_types_args
    assert isinstance(key, keys._HashedTuple)


def test_typedmethodkey_behaves_like_typedkey():
    class Dummy:
        pass

    dummy = Dummy()
    key_via_method = keys.typedmethodkey(dummy, 5, flag=False)
    key_direct = keys.typedkey(5, flag=False)
    assert key_via_method == key_direct
    assert isinstance(key_via_method, keys._HashedTuple)


def test_hashedtuple_addition_and_raddition():
    base = keys._HashedTuple((1, 2))
    added = base + (3, 4)
    radded = (5, 6) + base

    assert isinstance(added, keys._HashedTuple)
    assert isinstance(radded, keys._HashedTuple)

    # Verify the resulting contents
    assert tuple(added) == (1, 2, 3, 4)
    assert tuple(radded) == (5, 6, 1, 2)


def test_hashkey_empty_arguments():
    # Edge case: no positional or keyword arguments
    key = keys.hashkey()
    assert isinstance(key, keys._HashedTuple)
    assert tuple(key) == ()
    # Hash should still work and be cached
    first = hash(key)
    second = hash(key)
    assert first == second
