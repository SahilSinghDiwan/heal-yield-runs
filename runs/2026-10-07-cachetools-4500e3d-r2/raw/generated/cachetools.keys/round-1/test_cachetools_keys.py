import builtins

import pytest
from cachetools import keys


def test_hashkey_without_kwargs_is_hashed_tuple_and_caches_hash():
    # Simple positional arguments should produce a _HashedTuple
    k1 = keys.hashkey(1, "a", (2, 3))
    k2 = keys.hashkey(1, "a", (2, 3))

    # Both keys should be instances of the custom tuple subclass
    assert isinstance(k1, keys._HashedTuple)
    assert isinstance(k2, keys._HashedTuple)

    # Equality should hold for identical arguments
    assert k1 == k2

    # Hash should be cached (i.e., calling hash multiple times returns same value)
    h1 = hash(k1)
    h2 = hash(k1)
    assert h1 == h2


def test_hashkey_with_kwargs_includes_kwmark_and_is_order_independent():
    # Two calls with kwargs in different order should produce equal keys
    k1 = keys.hashkey(1, b=2, a=3)
    k2 = keys.hashkey(1, a=3, b=2)

    # Both should be _HashedTuple instances
    assert isinstance(k1, keys._HashedTuple)
    assert isinstance(k2, keys._HashedTuple)

    # Equality should hold despite different kw order
    assert k1 == k2

    # The sentinel _kwmark is represented by the _HashedTuple class itself.
    sentinel = keys._HashedTuple
    flat = list(k1)

    # The sentinel should appear exactly once between positional args and kwargs
    assert flat.count(sentinel) == 1
    # Its position should be after the first positional argument (index 1)
    assert flat[1] is sentinel


def test_methodkey_ignores_self_and_matches_hashkey():
    class Dummy:
        pass

    dummy = Dummy()
    # methodkey should ignore the first argument (self) and behave like hashkey
    mk = keys.methodkey(dummy, 10, x=5)
    hk = keys.hashkey(10, x=5)

    assert isinstance(mk, keys._HashedTuple)
    assert mk == hk

    # Ensure that the sentinel (the _HashedTuple class) is present when kwargs are used
    sentinel = keys._HashedTuple
    assert sentinel in mk


def test_typedkey_appends_type_information():
    # Typed key should include type info for both positional and keyword args
    k = keys.typedkey(1, "a", flag=True, count=5)

    # The key should be a _HashedTuple
    assert isinstance(k, keys._HashedTuple)

    # The last elements should be the types of the positional arguments
    assert k[-1] is int
    assert k[-2] is str

    # Types for keyword values should appear before the positional types
    # Find the sentinel position to locate where kw types start
    sentinel = keys._HashedTuple
    flat = list(k)
    sentinel_index = flat.index(sentinel)

    # After the sentinel, we have the sorted kw items, then kw types, then positional types
    # Verify that the kw value types are present
    kw_type_section = flat[sentinel_index + 1 + len(sorted({"flag": True, "count": 5}.items())) : sentinel_index + 1 + len(sorted({"flag": True, "count": 5}.items())) + 2]
    assert bool in kw_type_section  # type of True
    assert int in kw_type_section   # type of 5


def test_typedmethodkey_behaves_like_typedkey():
    class Foo:
        pass

    foo = Foo()
    # typedmethodkey should ignore self and delegate to typedkey
    mk = keys.typedmethodkey(foo, 3.14, flag=True)
    hk = keys.typedkey(3.14, flag=True)

    assert mk == hk
    assert isinstance(mk, keys._HashedTuple)

    # Verify that type information for both positional and kw args is present
    # The last element should be the type of the positional arg (float)
    assert mk[-1] is float

    # The sentinel is the _HashedTuple class; locate it to find kw types
    sentinel = keys._HashedTuple
    flat = list(mk)
    sentinel_index = flat.index(sentinel)

    # After the sentinel, we have the sorted kw items, then kw types
    # For the kw arg 'flag=True', the type bool should appear after the kw items
    kw_items_len = len(sorted({"flag": True}.items()))
    kw_type = flat[sentinel_index + 1 + kw_items_len]
    assert kw_type is bool
