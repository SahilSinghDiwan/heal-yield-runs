import pickle

import pytest

from cachetools import keys


def test_hashkey_simple_args():
    key = keys.hashkey(1, "a", (2, 3))
    assert isinstance(key, keys._HashedTuple)
    assert key == (1, "a", (2, 3))


def test_hashkey_with_kwargs_and_sorting():
    key1 = keys.hashkey(1, b=2, a=3)
    key2 = keys.hashkey(1, a=3, b=2)
    # kwargs are sorted, so the keys should be equal
    assert key1 == key2
    # ensure the sentinel is present
    assert keys._kwmark in key1


def test_hashkey_hash_caching():
    key = keys.hashkey("x", 42)
    # before hashing, the internal cache should be None
    assert getattr(key, "_HashedTuple__hashvalue") is None
    first = hash(key)
    # after first hash, the cache should be set
    cached = getattr(key, "_HashedTuple__hashvalue")
    assert cached == first
    # subsequent hashes return the same value without recomputing
    assert hash(key) == first
    assert getattr(key, "_HashedTuple__hashvalue") == cached


def test_methodkey_ignores_self():
    class Dummy:
        pass

    dummy = Dummy()
    key = keys.methodkey(dummy, 10, foo="bar")
    # methodkey should behave like hashkey without the self argument
    expected = keys.hashkey(10, foo="bar")
    assert key == expected
    assert isinstance(key, keys._HashedTuple)


def test_typedkey_without_kwargs():
    key = keys.typedkey(1, "a")
    # types are appended after the original values
    assert key == (1, "a", int, str)


def test_typedkey_with_kwargs():
    key = keys.typedkey(1, a="b", c=3)
    # order: args, sentinel, sorted kwargs, types of kw values, types of args
    expected = (
        1,
        keys._kwmark,
        ("a", "b"),
        ("c", 3),
        str,
        int,
        int,
    )
    assert key == expected


def test_typedmethodkey_behaviour():
    class Dummy:
        pass

    dummy = Dummy()
    key = keys.typedmethodkey(dummy, 5, flag=True)
    expected = keys.typedkey(5, flag=True)
    assert key == expected
    assert isinstance(key, keys._HashedTuple)


def test_empty_calls_return_empty_hashedtuple():
    assert keys.hashkey() == ()
    assert keys.typedkey() == ()


def test_hashedtuple_addition_preserves_type():
    base = keys._HashedTuple((1, 2))
    added = base + (3, 4)
    assert isinstance(added, keys._HashedTuple)
    assert added == (1, 2, 3, 4)
    radded = (0,) + base
    assert isinstance(radded, keys._HashedTuple)
    assert radded == (0, 1, 2)


def test_typedkey_distinguishes_bool_int():
    # bool is a subclass of int but should be distinguished by type
    key_int = keys.typedkey(1)
    key_bool = keys.typedkey(True)
    assert key_int != key_bool
    # Ensure the type information is present
    assert key_int[-1] is int
    assert key_bool[-1] is bool


def test_typedkey_kwargs_type_distinction():
    key_num = keys.typedkey(val=1)
    key_str = keys.typedkey(val="1")
    assert key_num != key_str
    # The type part of the key should differ
    assert key_num[-2] is int
    assert key_str[-2] is str


def test_hashedtuple_hash_caching_internal():
    key = keys.hashkey("test")
    # internal cache should start as None
    assert getattr(key, "_HashedTuple__hashvalue") is None
    # compute hash
    h1 = hash(key)
    # now cache should be set
    cached = getattr(key, "_HashedTuple__hashvalue")
    assert cached == h1
    # second hash returns same value
    assert hash(key) == h1


def test_pickle_hashedtuple():
    original = keys.hashkey(1, a=2)
    data = pickle.dumps(original)
    restored = pickle.loads(data)
    # Restored object should be a _HashedTuple and equal to original
    assert isinstance(restored, keys._HashedTuple)
    assert restored == original
    # Hash should still work after unpickling
    assert hash(restored) == hash(original)
