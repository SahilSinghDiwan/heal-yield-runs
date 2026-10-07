import builtins

import pytest

# Import the module under test using its dotted path
import cachetools.keys as keys


def test_hashkey_without_kwargs_hash_caching():
    """Ensure that hashkey returns a _HashedTuple and that its hash is cached."""
    key = keys.hashkey(1, 2, 3)
    assert isinstance(key, keys._HashedTuple)

    # First hash computation
    first_hash = hash(key)
    # Subsequent hash should be the same object (cached)
    second_hash = hash(key)
    assert first_hash == second_hash
    # The internal cache should have been set (no exception on repeated hash)
    assert key.__hash__() == first_hash


def test_hashkey_with_kwargs_order_and_sentinel():
    """Kwargs order should not affect the resulting key and the sentinel should be present."""
    key1 = keys.hashkey(1, b=2, a=3)
    key2 = keys.hashkey(1, a=3, b=2)
    assert key1 == key2
    assert isinstance(key1, keys._HashedTuple)

    # The sentinel element is the _HashedTuple class itself (inserted via _kwmark)
    sentinel_class = keys._HashedTuple
    # It should appear exactly once and be the second element (index 1) after the positional arg(s)
    assert key1[1] is sentinel_class
    assert tuple(key1).count(sentinel_class) == 1


def test_methodkey_ignores_self():
    """methodkey should ignore the bound instance and behave like hashkey."""
    class Dummy:
        pass

    dummy = Dummy()
    key = keys.methodkey(dummy, 42, foo="bar")
    # methodkey forwards to hashkey, so the result should be identical to calling hashkey directly
    expected = keys.hashkey(42, foo="bar")
    assert key == expected
    assert isinstance(key, keys._HashedTuple)


def test_typedkey_without_kwargs():
    """typedkey without kwargs should append types of positional arguments."""
    key = keys.typedkey(10, "test")
    # Expected: (10, "test") + (int, str)
    expected = (10, "test", int, str)
    assert tuple(key) == expected
    assert isinstance(key, keys._HashedTuple)


def test_typedkey_with_kwargs_and_type_order():
    """typedkey with mixed args and kwargs should preserve order and include type information."""
    key = keys.typedkey(1, a="x", b=2)

    # Build the expected tuple step by step
    sentinel_class = keys._HashedTuple
    sorted_kwargs = (("a", "x"), ("b", 2))
    # Base part: positional args + sentinel class + sorted kwargs
    expected_base = (1, sentinel_class) + sorted_kwargs
    # Types of kwargs values, in the same order as sorted_kwargs
    expected_kw_types = (str, int)
    # Types of positional args
    expected_arg_types = (int,)

    expected = expected_base + expected_kw_types + expected_arg_types

    assert isinstance(key, keys._HashedTuple)
    assert tuple(key) == expected
    # Ensure the sentinel class appears exactly once
    assert tuple(key).count(sentinel_class) == 1


def test_typedmethodkey_behaves_like_typedkey():
    """typedmethodkey should delegate to typedkey, ignoring the bound instance."""
    class Dummy:
        pass

    dummy = Dummy()
    key = keys.typedmethodkey(dummy, 3.14, flag=True)
    expected = keys.typedkey(3.14, flag=True)
    assert key == expected
    assert isinstance(key, keys._HashedTuple)


def test_hashedtuple_addition_and_raddition():
    """_HashedTuple should support addition and right‑addition, returning new _HashedTuple instances."""
    base = keys._HashedTuple((1, 2))
    added = base + (3, 4)
    radded = (5, 6) + base

    assert isinstance(added, keys._HashedTuple)
    assert isinstance(radded, keys._HashedTuple)
    assert tuple(added) == (1, 2, 3, 4)
    assert tuple(radded) == (5, 6, 1, 2)

    # Ensure that hash caching works for the new tuples as well
    h1 = hash(added)
    h2 = hash(added)
    assert h1 == h2
    h3 = hash(radded)
    h4 = hash(radded)
    assert h3 == h4


def test_hashkey_empty_arguments():
    """hashkey with no arguments should return an empty _HashedTuple."""
    key = keys.hashkey()
    assert isinstance(key, keys._HashedTuple)
    assert len(key) == 0
    # Hash of an empty tuple should be consistent
    assert hash(key) == hash(())
