import pytest
import cachetools.keys as ck


def test_hashkey_simple_args():
    key = ck.hashkey(1, 2, "a")
    # The key should be an instance of the internal _HashedTuple.
    assert isinstance(key, ck._HashedTuple)
    # Its contents should match the provided positional arguments.
    assert tuple(key) == (1, 2, "a")
    # Hashing the key twice should yield the same cached hash value.
    h1 = hash(key)
    h2 = hash(key)
    assert h1 == h2


def test_hashkey_with_kwargs_and_sorting():
    # Keyword arguments are sorted and separated by the sentinel.
    key = ck.hashkey(1, b=2, a=3)
    # The sentinel class appears as the second element of the tuple.
    assert ck._HashedTuple in key
    # The full tuple representation should reflect sorted kwargs.
    assert tuple(key) == (1, ck._HashedTuple, ("a", 3), ("b", 2))


def test_hashkey_hash_caching():
    key = ck.hashkey("x")
    h1 = hash(key)
    h2 = hash(key)
    assert h1 == h2


def test_methodkey_ignores_self():
    class Dummy:
        pass

    dummy = Dummy()
    # methodkey forwards to hashkey, ignoring the first (self) argument.
    key = ck.methodkey(dummy, 10, foo="bar")
    expected = ck.hashkey(10, foo="bar")
    assert key == expected


def test_typedkey_without_kwargs():
    key = ck.typedkey(1, "s")
    # Types of the positional arguments are appended at the end.
    assert tuple(key)[-2:] == (int, str)


def test_typedkey_with_kwargs():
    key = ck.typedkey(1, flag=True, name="bob")
    tup = tuple(key)
    # The sentinel class should be present in the tuple.
    assert ck._HashedTuple in tup
    # Types for both positional and keyword arguments should be present.
    assert int in tup
    assert bool in tup
    assert str in tup


def test_typedmethodkey_behaviour():
    class Foo:
        pass

    foo = Foo()
    # typedmethodkey should ignore the first argument (self) like typedkey.
    key1 = ck.typedmethodkey(foo, 3.14, flag=False)
    key2 = ck.typedkey(3.14, flag=False)
    assert key1 == key2
    # Types are appended at the end; order is kwarg types then arg types.
    tup = tuple(key2)
    assert tup[-2:] == (bool, float) or tup[-2:] == (float, bool)


def test_empty_calls_return_empty_hashedtuple():
    key = ck.hashkey()
    assert isinstance(key, ck._HashedTuple)
    assert len(key) == 0


def test_hashedtuple_addition_preserves_type():
    a = ck._HashedTuple((1, 2))
    b = a + (3,)
    assert isinstance(b, ck._HashedTuple)
    assert tuple(b) == (1, 2, 3)
