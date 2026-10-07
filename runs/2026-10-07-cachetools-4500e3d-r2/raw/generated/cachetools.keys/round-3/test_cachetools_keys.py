import builtins
import pickle

import pytest

# Import the module under test via its dotted path
from cachetools import keys


def test_hashkey_returns_hashedtuple_and_hash_is_cached():
    """hashkey should return a _HashedTuple whose hash is computed only once."""
    call_count = {"cnt": 0}

    class CountHash:
        def __hash__(self):
            call_count["cnt"] += 1
            return 42

        def __eq__(self, other):
            return isinstance(other, CountHash)

    # The object is hashable, so hashkey will succeed
    key = keys.hashkey(CountHash())
    # First hash computation
    first = hash(key)
    # Second hash should reuse cached value
    second = hash(key)
    assert first == second == 42
    # The __hash__ of the element should have been called exactly once
    assert call_count["cnt"] == 1


def test_hashedtuple_add_and_radd_return_hashedtuple():
    """_HashedTuple should preserve its type when added to other tuples."""
    a = keys.hashkey(1, 2)
    b = keys.hashkey(3, 4)

    # Using __add__
    c = a + b
    assert isinstance(c, keys._HashedTuple)
    assert tuple(c) == (1, 2, 3, 4)

    # Using __radd__ (tuple on the left)
    d = (0,) + a
    assert isinstance(d, keys._HashedTuple)
    assert tuple(d) == (0, 1, 2)


def test_methodkey_ignores_self_and_matches_hashkey():
    """methodkey should ignore the bound instance and behave like hashkey."""
    class Dummy:
        pass

    dummy1 = Dummy()
    dummy2 = Dummy()

    args = (1, "a")
    kwargs = {"x": 10, "y": "z"}

    key1 = keys.methodkey(dummy1, *args, **kwargs)
    key2 = keys.methodkey(dummy2, *args, **kwargs)
    expected = keys.hashkey(*args, **kwargs)

    assert key1 == key2 == expected
    # Ensure the returned object is a _HashedTuple
    assert isinstance(key1, keys._HashedTuple)


def test_typedkey_appends_type_information_correctly():
    """typedkey should append type information for both args and kwargs."""
    args = (1, "s")
    kwargs = {"b": 2.5, "a": [1, 2]}

    key = keys.typedkey(*args, **kwargs)

    # The base part (before type info) should match hashkey's structure
    base = keys._HashedTuple(args + keys._kwmark + tuple(sorted(kwargs.items())))
    # Types for kwargs values (sorted by key) then types for args
    expected_type_tail = (
        type(kwargs["a"]),
        type(kwargs["b"]),
        type(args[0]),
        type(args[1]),
    )
    # Verify the key consists of the base followed by the type tail
    assert isinstance(key, keys._HashedTuple)
    assert tuple(key)[: len(base)] == tuple(base)
    assert tuple(key)[len(base) :] == expected_type_tail


def test_typedmethodkey_behaves_like_typedkey():
    """typedmethodkey should delegate to typedkey, ignoring the instance."""
    class Foo:
        pass

    foo1 = Foo()
    foo2 = Foo()

    args = (True,)
    kwargs = {"z": None, "y": 0}

    key1 = keys.typedmethodkey(foo1, *args, **kwargs)
    key2 = keys.typedmethodkey(foo2, *args, **kwargs)
    expected = keys.typedkey(*args, **kwargs)

    assert key1 == key2 == expected
    assert isinstance(key1, keys._HashedTuple)


def test_kwmark_is_unique_and_preserves_identity():
    """The kwmark sentinel should be a unique tuple containing the _HashedTuple class."""
    kwmark = keys._kwmark
    # It should be a tuple of length 1 containing the class object
    assert isinstance(kwmark, tuple) and len(kwmark) == 1
    assert kwmark[0] is keys._HashedTuple

    # Ensure that the sentinel is the same object used inside hashkey
    key = keys.hashkey(1, kw=2)
    # The kwmark should appear exactly once in the underlying tuple representation
    assert kwmark in (key[: len(key)]) or kwmark in (key[-len(kwmark) :])
