import builtins
import pickle
import types

import pytest

# Import the module under test
import cachetools.keys as keys


def test_hashkey_returns_hashed_tuple_and_is_hashable():
    k = keys.hashkey(1, "a", b=2)
    # It should be an instance of the internal _HashedTuple subclass
    assert isinstance(k, keys._HashedTuple)
    # It should also be a tuple
    assert isinstance(k, tuple)
    # The tuple should contain the positional args, the sentinel, and sorted kwargs
    expected = (1, "a") + keys._kwmark + (("b", 2),)
    assert tuple(k) == expected
    # It must be hashable and the hash should be stable across calls
    h1 = hash(k)
    h2 = hash(k)
    assert h1 == h2
    # A different key with same logical content should compare equal and have same hash
    k2 = keys.hashkey(1, "a", b=2)
    assert k == k2
    assert hash(k2) == h1


def test_hashkey_kwargs_order_independence():
    # Different ordering of kwargs should produce equal keys
    k1 = keys.hashkey(1, x=10, y=20)
    k2 = keys.hashkey(1, y=20, x=10)
    assert k1 == k2
    assert hash(k1) == hash(k2)
    # The sentinel should appear exactly once
    sentinel_count = tuple(k1).count(keys._kwmark)
    assert sentinel_count == 1


def test_hashkey_no_arguments():
    # Empty call should return an empty _HashedTuple
    k = keys.hashkey()
    assert isinstance(k, keys._HashedTuple)
    assert len(k) == 0
    # Hash of empty tuple is well‑defined
    assert hash(k) == hash(())


def test_hashkey_unhashable_argument_raises_type_error():
    # Lists are unhashable, so hashkey should raise TypeError when trying to hash
    with pytest.raises(TypeError):
        keys.hashkey([1, 2, 3])


def test_methodkey_ignores_self():
    class Dummy:
        pass

    d1 = Dummy()
    d2 = Dummy()
    # methodkey should ignore the self argument entirely
    k1 = keys.methodkey(d1, 1, 2, flag=True)
    k2 = keys.methodkey(d2, 1, 2, flag=True)
    assert k1 == k2
    assert hash(k1) == hash(k2)


def test_typedkey_includes_type_information():
    # Positional arguments only
    k = keys.typedkey(10, "s")
    # Base part should be the positional args
    assert tuple(k[:2]) == (10, "s")
    # Followed by the types of the positional args
    assert tuple(k[2:]) == (int, str)

    # With kwargs
    k2 = keys.typedkey(10, a="x", b=3.14)
    # Expected layout:
    # (10) + sentinel + sorted kwargs + types of kwargs + types of args
    sorted_items = tuple(sorted({"a": "x", "b": 3.14}.items()))
    expected_base = (10,) + keys._kwmark + sorted_items
    assert tuple(k2[: len(expected_base)]) == expected_base
    # Types for kwargs (str, float) then type for positional arg (int)
    expected_types = (str, float, int)
    assert tuple(k2[-len(expected_types) :]) == expected_types


def test_typedmethodkey_forwards_to_typedkey():
    class Dummy:
        pass

    d = Dummy()
    # typedmethodkey should produce the same result as typedkey for the same args
    k1 = keys.typedmethodkey(d, 5, flag=False)
    k2 = keys.typedkey(5, flag=False)
    assert k1 == k2
    assert hash(k1) == hash(k2)


def test_hashedtuple_addition_and_raddition():
    base = keys._HashedTuple((1, 2))
    added = base + (3, 4)
    # Result should be a new _HashedTuple containing concatenated elements
    assert isinstance(added, keys._HashedTuple)
    assert tuple(added) == (1, 2, 3, 4)

    # __radd__ should also work
    added2 = (0,) + base
    assert isinstance(added2, keys._HashedTuple)
    assert tuple(added2) == (0, 1, 2)


def test_hashedtuple_pickle_roundtrip():
    # Ensure that a _HashedTuple can be pickled and unpickled correctly
    original = keys.hashkey(42, name="answer")
    data = pickle.dumps(original)
    restored = pickle.loads(data)
    # The restored object should compare equal and have the same hash
    assert restored == original
    assert hash(restored) == hash(original)


def test_hash_consistency_across_multiple_calls():
    # Repeated hashing of the same key should not change the cached hash value
    k = keys.hashkey("test")
    first_hash = hash(k)
    for _ in range(5):
        assert hash(k) == first_hash
