import pytest
from cachetools import keys


def test_hashkey_without_kwargs_is_hashed_tuple_and_caches_hash():
    # Simple positional arguments should produce a _HashedTuple
    k = keys.hashkey(1, "a", (2, 3))
    assert isinstance(k, keys._HashedTuple)

    # The hash should be cached: calling hash() multiple times yields the same value
    first_hash = hash(k)
    second_hash = hash(k)
    assert first_hash == second_hash


def test_hashkey_with_kwargs_includes_kwmark_and_is_order_independent():
    # Keyword arguments should be sorted and separated by the sentinel
    k1 = keys.hashkey(1, a=2, b=3)
    k2 = keys.hashkey(1, b=3, a=2)
    assert k1 == k2

    # The sentinel should be present exactly once
    sentinel = keys._kwmark[0]
    assert k1.count(sentinel) == 1


def test_methodkey_ignores_self_and_matches_hashkey():
    class Dummy:
        def __init__(self, val):
            self.val = val

        def method(self, *args, **kwargs):
            return keys.methodkey(self, *args, **kwargs)

    d = Dummy(10)
    # methodkey should ignore the bound instance and behave like hashkey
    expected = keys.hashkey(1, 2, foo="bar")
    actual = d.method(1, 2, foo="bar")
    assert actual == expected
    assert isinstance(actual, keys._HashedTuple)


def test_typedkey_appends_type_information():
    # Typed key should include type info for both positional and keyword args
    k = keys.typedkey(1, "a", flag=True, count=5)

    # The key should be a _HashedTuple
    assert isinstance(k, keys._HashedTuple)

    # Positional argument types are appended at the very end, in order of the args
    assert k[-2:] == (int, str)

    # Keyword argument types are appended after the sorted keyword items
    sentinel = keys._kwmark[0]
    kw_index = k.index(sentinel)

    # Sorted keyword items (by key name)
    sorted_kwargs = tuple(sorted({"flag": True, "count": 5}.items()))
    kw_type_start = kw_index + 1 + len(sorted_kwargs)

    # Types for the sorted keyword values (count -> int, flag -> bool)
    assert k[kw_type_start:kw_type_start + 2] == (int, bool)


def test_typedmethodkey_behaves_like_typedkey():
    class Dummy:
        def __init__(self, val):
            self.val = val

        def method(self, *args, **kwargs):
            return keys.typedmethodkey(self, *args, **kwargs)

    d = Dummy(10)
    expected = keys.typedkey(1, 2, foo="bar")
    actual = d.method(1, 2, foo="bar")
    assert actual == expected
    assert isinstance(actual, keys._HashedTuple)
