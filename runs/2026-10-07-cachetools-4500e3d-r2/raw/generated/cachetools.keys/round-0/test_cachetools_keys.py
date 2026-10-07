import builtins
import types

import pytest

# Import the module under test
import cachetools.keys as keys


def test_hashkey_without_kwargs_is_hashed_tuple_and_caches_hash():
    # Simple positional arguments
    k = keys.hashkey(1, "a", (2, 3))
    # The returned object should be an instance of the private _HashedTuple class
    assert isinstance(k, keys._HashedTuple)

    # Before hashing, the internal cache should be None
    # The mangled name for the private attribute is _HashedTuple__hashvalue
    assert getattr(k, "_HashedTuple__hashvalue") is None

    # First hash call computes and caches the value
    h1 = hash(k)
    cached = getattr(k, "_HashedTuple__hashvalue")
    assert cached == h1

    # Subsequent hash calls return the cached value without recomputing
    # (We cannot directly count calls to tuple.__hash__, but we can ensure the value is unchanged)
    h2 = hash(k)
    assert h2 == h1
    assert getattr(k, "_HashedTuple__hashvalue") == h1


def test_hashkey_with_kwargs_includes_kwmark_and_is_order_independent():
    # Two calls with kwargs in different order should produce equal keys
    k1 = keys.hashkey(1, b=2, a=3)
    k2 = keys.hashkey(1, a=3, b=2)

    # Both should be _HashedTuple instances
    assert isinstance(k1, keys._HashedTuple)
    assert isinstance(k2, keys._HashedTuple)

    # Equality should hold despite different kw order
    assert k1 == k2

    # The sentinel _kwmark should appear exactly once between args and kwargs
    # Since _kwmark is a tuple containing the _HashedTuple class, we can check identity
    sentinel = keys._kwmark
    # Convert to list for easier inspection
    flat = list(k1)
    # Find the sentinel position
    idx = flat.index(sentinel)
    # Ensure that everything before idx are the positional args
    assert tuple(flat[:idx]) == (1,)
    # Ensure that after sentinel we have the sorted kw items
    # sorted items are [('a', 3), ('b', 2)]
    assert tuple(flat[idx + 1 :]) == (("a", 3), ("b", 2))


def test_methodkey_ignores_self_and_matches_hashkey():
    class Dummy:
        pass

    dummy = Dummy()
    # methodkey should ignore the first argument (self) and behave like hashkey
    mk = keys.methodkey(dummy, 10, x=5)
    hk = keys.hashkey(10, x=5)

    assert isinstance(mk, keys._HashedTuple)
    assert mk == hk
    # Ensure that the sentinel is present when kwargs are used
    assert keys._kwmark in mk


def test_typedkey_appends_type_information():
    # Positional arguments only
    k = keys.typedkey(10, "foo")
    # Expected: original args + types of args
    expected = keys._HashedTuple((10, "foo")) + (int, str)
    assert k == expected

    # With kwargs: types for kwargs values are appended after the kw items,
    # then types for positional args are appended at the end.
    k2 = keys.typedkey(1, a=2, b="x")
    # Build expected manually
    sorted_kwargs = tuple(sorted({"a": 2, "b": "x"}.items()))  # (('a', 2), ('b', 'x'))
    base = keys._HashedTuple((1,) + keys._kwmark + sorted_kwargs)
    # Append types of kw values in the same order as sorted_kwargs
    base += tuple(type(v) for _, v in sorted_kwargs)
    # Finally append types of positional args
    base += (int,)
    assert k2 == base

    # Ensure that different types affect equality
    k_int = keys.typedkey(1)
    k_str = keys.typedkey("1")
    assert k_int != k_str
    # Their hash values should also differ
    assert hash(k_int) != hash(k_str)


def test_typedmethodkey_behaves_like_typedkey():
    class Foo:
        pass

    foo = Foo()
    # typedmethodkey should ignore self and delegate to typedkey
    mk = keys.typedmethodkey(foo, 3.14, flag=True)
    hk = keys.typedkey(3.14, flag=True)
    assert mk == hk
    # Verify that type information for both positional and kw args is present
    # The last element of the key should be the type of the positional arg (float)
    assert mk[-1] is float
    # The type of the kw value (bool) should appear before the positional types
    # Find the position of the sentinel to locate kw types
    sentinel_index = list(mk).index(keys._kwmark)
    # Types for kw values start after the kw items (which are after sentinel)
    kw_items_len = len(tuple(sorted({"flag": True}.items())))
    kw_type_start = sentinel_index + 1 + kw_items_len
    assert mk[kw_type_start] is bool
