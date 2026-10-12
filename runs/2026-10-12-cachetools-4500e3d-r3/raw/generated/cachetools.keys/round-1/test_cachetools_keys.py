import pickle
import builtins

import pytest

# Import the module under test via its dotted path.
from cachetools import keys as ck


def test_hashkey_simple_args():
    # Simple positional arguments should produce a _HashedTuple
    key = ck.hashkey(1, "a", (2, 3))
    assert isinstance(key, tuple)
    # The underlying type should be the private _HashedTuple subclass
    assert type(key).__name__ == "_HashedTuple"
    # The content should match the input arguments
    assert key == (1, "a", (2, 3))


def test_hashkey_with_kwargs_and_sorting():
    # Keyword arguments should be sorted and separated by the sentinel.
    key = ck.hashkey(1, b=2, a=3)
    # The sentinel is a tuple containing the _HashedTuple class.
    sentinel = ck._kwmark
    # Ensure the sentinel appears exactly once and in the correct position.
    assert sentinel in key
    idx = key.index(sentinel)
    # Arguments before the sentinel are the positional args.
    assert key[:idx] == (1,)
    # After the sentinel we should have the sorted kw items.
    sorted_items = tuple(sorted({"a": 3, "b": 2}.items()))
    assert key[idx + 1 : idx + 1 + len(sorted_items)] == sorted_items
    # No extra elements.
    assert len(key) == 1 + 1 + len(sorted_items)


def test_hashkey_hash_caching():
    # Verify that the hash value is cached after the first call.
    key = ck.hashkey("x", 42)
    # Access the mangled attribute that stores the cached hash.
    cache_attr = "_HashedTuple__hashvalue"
    # Initially it should be None.
    assert getattr(key, cache_attr) is None
    # Compute hash once.
    h1 = hash(key)
    # Now the cached value should be set.
    cached = getattr(key, cache_attr)
    assert cached == h1
    # Subsequent hash calls should return the same value without recomputation.
    h2 = hash(key)
    assert h2 == h1


def test_methodkey_ignores_self():
    class Dummy:
        pass

    dummy = Dummy()
    # methodkey should ignore the first argument (self) and behave like hashkey.
    key1 = ck.methodkey(dummy, 10, flag=True)
    key2 = ck.hashkey(10, flag=True)
    assert key1 == key2
    # Ensure the types are still _HashedTuple.
    assert isinstance(key1, tuple)
    assert type(key1).__name__ == "_HashedTuple"


def test_typedkey_without_kwargs():
    key = ck.typedkey(1, "a")
    # Types of arguments should be appended.
    expected = (1, "a", int, str)
    assert tuple(key) == expected
    # Verify that the key is a _HashedTuple.
    assert type(key).__name__ == "_HashedTuple"


def test_typedkey_with_kwargs():
    key = ck.typedkey(1, x=2, y="z")
    # Build expected components.
    sentinel = ck._kwmark
    sorted_items = tuple(sorted({"x": 2, "y": "z"}.items()))
    # Types for kwargs values.
    kw_types = tuple(type(v) for _, v in sorted_items)
    # Types for positional args.
    pos_types = tuple(type(v) for v in (1,))
    # Assemble expected tuple.
    expected = (1,) + sentinel + sorted_items + kw_types + pos_types
    assert tuple(key) == expected
    # Ensure the key is hashable.
    assert isinstance(hash(key), int)


def test_typedmethodkey_behaviour():
    class Foo:
        pass

    foo = Foo()
    # typedmethodkey should ignore the first argument (self) like typedkey.
    key1 = ck.typedmethodkey(foo, 3.14, flag=False)
    key2 = ck.typedkey(3.14, flag=False)
    assert key1 == key2
    # Types should be correctly appended.
    expected = (3.14, False, float, bool)
    assert tuple(key2) == expected


def test_empty_calls_return_empty_hashedtuple():
    # No arguments should yield an empty _HashedTuple.
    key = ck.hashkey()
    assert isinstance(key, tuple)
    assert len(key) == 0
    assert type(key).__name__ == "_HashedTuple"
    # Its hash should be the same as hash of an empty tuple.
    assert hash(key) == hash(())


def test_hashedtuple_addition_preserves_type():
    a = ck._HashedTuple((1, 2))
    b = ck._HashedTuple((3,))
    c = a + b
    d = (1, 2) + (3,)
    assert isinstance(c, ck._HashedTuple)
    assert tuple(c) == d
    # Reverse addition also yields _HashedTuple.
    e = (0,) + a
    assert isinstance(e, ck._HashedTuple)
    assert tuple(e) == (0, 1, 2)


def test_pickle_roundtrip_preserves_key():
    original = ck.typedkey(10, name="bob")
    data = pickle.dumps(original)
    restored = pickle.loads(data)
    # The restored key should compare equal and be of the same type.
    assert restored == original
    assert type(restored).__name__ == "_HashedTuple"
    # Hashes should match.
    assert hash(restored) == hash(original)


def test_hashkey_with_unhashable_argument_raises_on_hash():
    # Creating a key with an unhashable element (list) should succeed,
    # but hashing it must raise a TypeError.
    key = ck.hashkey([1, 2, 3])
    assert isinstance(key, tuple)
    with pytest.raises(TypeError):
        hash(key)


def test_typedkey_with_unhashable_argument_raises_on_hash():
    # Even with types appended, an unhashable argument should cause hashing to fail.
    key = ck.typedkey([1, 2])
    assert isinstance(key, tuple)
    with pytest.raises(TypeError):
        hash(key)


def test_kwmark_is_unique_and_immutable():
    # The sentinel should be a tuple containing the _HashedTuple class.
    sentinel = ck._kwmark
    assert isinstance(sentinel, tuple)
    assert sentinel == (ck._HashedTuple,)
    # Its identity should be stable.
    assert sentinel is ck._kwmark
    # Attempting to modify it should raise an exception.
    with pytest.raises(AttributeError):
        sentinel[0] = builtins.int
