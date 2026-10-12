import pytest
from cachetools import keys


def test_hashkey_positional_only():
    k = keys.hashkey(1, "a")
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == (1, "a")


def test_hashkey_with_kwargs_and_ordering():
    k = keys.hashkey(1, b=2, a=3)
    # kwargs are sorted by key name, so order becomes a then b
    expected = (1,) + keys._kwmark + (("a", 3), ("b", 2))
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == expected


def test_methodkey_ignores_self():
    class Dummy:
        def get_key(self, *args, **kwargs):
            return keys.methodkey(self, *args, **kwargs)

    d = Dummy()
    k = d.get_key(5, x=6)
    expected = keys.hashkey(5, x=6)
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == tuple(expected)


def test_typedkey_positional_only():
    k = keys.typedkey(1, "a")
    # base args followed by their types
    expected = (1, "a") + (int, str)
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == expected


def test_typedkey_with_kwargs():
    # Provide kwargs out of order to test sorting
    k = keys.typedkey(1, a=2, b="x")
    # Build expected step by step
    sorted_kwargs = (("a", 2), ("b", "x"))
    base = (1,) + keys._kwmark + sorted_kwargs
    # Append types of kw values then types of args
    expected = base + (int, str) + (int,)
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == expected
    # Ensure the kwmark sentinel is correctly placed
    assert k[1] is keys._kwmark[0]
    # Types order: first kwargs values, then positional args
    assert tuple(k[-3:]) == (int, str, int)


def test_typedmethodkey_forwards_to_typedkey():
    class Dummy:
        def get_key(self, *args, **kwargs):
            return keys.typedmethodkey(self, *args, **kwargs)

    d = Dummy()
    k = d.get_key(1, a=2)
    expected = keys.typedkey(1, a=2)
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == tuple(expected)


def test_hash_consistency_across_calls():
    k1 = keys.hashkey(1, 2, a=3)
    k2 = keys.hashkey(1, 2, a=3)
    assert hash(k1) == hash(k2)
    # Ensure hash is cached on the same object
    h1 = hash(k1)
    h2 = hash(k1)
    assert h1 == h2


def test_empty_arguments():
    k = keys.hashkey()
    assert isinstance(k, keys._HashedTuple)
    assert tuple(k) == ()
    tk = keys.typedkey()
    assert isinstance(tk, keys._HashedTuple)
    assert tuple(tk) == ()
