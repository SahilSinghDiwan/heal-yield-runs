import pickle

import pytest

# Import the module under test using its dotted path
from cachetools import keys


def test_hashkey_unhashable_argument_raises():
    """hashkey should raise TypeError when any argument is unhashable."""
    unhashable = [1, 2, 3]  # list is unhashable
    with pytest.raises(TypeError):
        keys.hashkey(unhashable)


def test_typedkey_unhashable_argument_raises():
    """typedkey should raise TypeError when any argument is unhashable."""
    unhashable = {1: "a"}  # dict is unhashable
    with pytest.raises(TypeError):
        keys.typedkey(unhashable)


def test_typedkey_only_kwargs_includes_correct_type_order():
    """
    When only keyword arguments are supplied, typedkey must include the
    types of the kwarg values (in sorted key order) and no extra
    positional‑argument types.
    """
    kw = {"b": 10, "a": "x"}
    # Build the expected key step by step
    # 1. args part is empty tuple
    # 2. sentinel
    sentinel = keys._kwmark
    # 3. sorted kwargs items
    sorted_items = tuple(sorted(kw.items()))
    # 4. types for kwargs values in the same order
    kw_types = tuple(type(v) for _, v in sorted_items)

    expected = keys._HashedTuple(() + sentinel + sorted_items) + kw_types
    result = keys.typedkey(**kw)

    assert isinstance(result, keys._HashedTuple)
    assert result == expected
    # Ensure the hash can be computed (i.e., the key is hashable)
    assert isinstance(hash(result), int)


def test_hashedtuple_pickle_roundtrip():
    """
    A _HashedTuple should survive a pickle round‑trip, preserving both
    equality and hash value.
    """
    original = keys._HashedTuple((1, "a", (2, 3)))
    # Compute hash before pickling to trigger caching
    pre_hash = hash(original)

    data = pickle.dumps(original)
    restored = pickle.loads(data)

    # Equality and hash must match the original
    assert restored == original
    assert hash(restored) == pre_hash
    # The restored object should also be an instance of _HashedTuple
    assert isinstance(restored, keys._HashedTuple)


def test_hashkey_multiple_hash_calls_return_same_value():
    """
    The hash of a _HashedTuple should be cached; calling hash repeatedly
    must return the same integer without recomputing.
    """
    key = keys.hashkey(1, 2, a=3)
    first = hash(key)
    second = hash(key)
    assert first == second
    # The cached hash value should be stored on the instance; we can
    # indirectly verify that the attribute exists after the first call.
    # (Accessing the private name is acceptable in tests.)
    assert getattr(key, "_HashedTuple__hashvalue") == first
