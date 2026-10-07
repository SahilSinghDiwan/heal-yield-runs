import threading
import types

import pytest
import cachetools._cached as cached


def simple_key(x):
    return x


def info_tuple(hits, misses):
    """Return a simple (hits, misses) tuple."""
    return (hits, misses)


@pytest.mark.parametrize(
    "wrapper_factory, args, kwargs, expected_hits, expected_misses",
    [
        # _uncached_info: cache is None, info provided
        (
            lambda: cached._wrapper(
                func=lambda x: x * 2,
                cache=None,
                key=simple_key,
                info=info_tuple,
            ),
            (1,),
            {},
            0,
            1,
        ),
        # _unlocked_info: cache provided, no lock/cond, info provided
        (
            lambda: cached._wrapper(
                func=lambda x: x * 2,
                cache={},
                key=simple_key,
                info=info_tuple,
            ),
            (2,),
            {},
            0,
            1,
        ),
        # _locked_info: cache with lock, info provided
        (
            lambda: cached._wrapper(
                func=lambda x: x * 2,
                cache={},
                key=simple_key,
                lock=threading.Lock(),
                info=info_tuple,
            ),
            (3,),
            {},
            0,
            1,
        ),
        # _condition_info: cache with lock and condition, info provided
        (
            lambda: cached._wrapper(
                func=lambda x: x * 2,
                cache={},
                key=simple_key,
                lock=threading.Lock(),
                cond=threading.Condition(),
                info=info_tuple,
            ),
            (4,),
            {},
            0,
            1,
        ),
    ],
)
def test_info_wrappers_counts_and_clearing(
    wrapper_factory, args, kwargs, expected_hits, expected_misses
):
    """
    Verify that wrappers created with an ``info`` callable correctly count hits
    and misses, and that ``cache_clear`` resets those counters.
    """
    wrapper = wrapper_factory()

    # First call: miss
    result1 = wrapper(*args, **kwargs)
    assert result1 == args[0] * 2

    # Second call with same argument: hit
    result2 = wrapper(*args, **kwargs)
    assert result2 == result1

    # Verify hit/miss counts via cache_info
    hits, misses = wrapper.cache_info()
    assert hits == expected_hits + 1  # one hit after the second call
    assert misses == expected_misses

    # Clear cache and counters
    wrapper.cache_clear()

    # After clearing, cache should be empty and counters reset
    assert wrapper.cache == {} or wrapper.cache is None
    hits_cleared, misses_cleared = wrapper.cache_info()
    assert hits_cleared == 0
    assert misses_cleared == 0

    # Subsequent call should be a miss again
    result3 = wrapper(*args, **kwargs)
    assert result3 == result1
    hits_after, misses_after = wrapper.cache_info()
    assert hits_after == 0
    assert misses_after == 1


def test_unlocked_wrapper_caches_and_counts_hits_misses():
    """Basic behavior of the unlocked wrapper without an info callable."""
    cache = {}
    wrapper = cached._wrapper(
        func=lambda x: x + 1,
        cache=cache,
        key=simple_key,
        lock=None,
        cond=None,
        info=None,
    )
    # cache_info should be None when no info callable is supplied
    assert wrapper.cache_info is None

    # First call: miss, value stored
    assert wrapper(10) == 11
    assert cache[10] == 11

    # Second call: hit, same result
    assert wrapper(10) == 11

    # Clear cache and ensure subsequent call is a miss again
    wrapper.cache_clear()
    assert cache == {}
    assert wrapper(10) == 11
    assert cache[10] == 11


def test_locked_wrapper_behaves_like_unlocked():
    """A locked wrapper should behave like the unlocked version regarding caching."""
    lock = threading.Lock()
    cache = {}
    wrapper = cached._wrapper(
        func=lambda x: x * 3,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=None,
        info=None,
    )
    assert wrapper.cache_info is None

    # First call stores the result
    assert wrapper(5) == 15
    assert cache[5] == 15

    # Second call retrieves from cache
    assert wrapper(5) == 15

    # Clear and verify cache is empty
    wrapper.cache_clear()
    assert cache == {}
    assert wrapper(5) == 15
    assert cache[5] == 15


def test_condition_wrapper_with_info_counts_hits_and_misses():
    """Condition wrapper should correctly count hits/misses and respect the condition."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    wrapper = cached._wrapper(
        func=lambda x: x - 1,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=cond,
        info=info_tuple,
    )
    # First call: miss
    assert wrapper(7) == 6
    # Second call: hit
    assert wrapper(7) == 6
    hits, misses = wrapper.cache_info()
    assert hits == 1
    assert misses == 1

    # Clear and verify counters reset
    wrapper.cache_clear()
    hits_cleared, misses_cleared = wrapper.cache_info()
    assert hits_cleared == 0
    assert misses_cleared == 0


def test_uncached_info_wrapper_counts_misses():
    """Uncached wrapper with info should only count misses."""
    wrapper = cached._wrapper(
        func=lambda x: x * x,
        cache=None,
        key=simple_key,
        info=info_tuple,
    )
    # Call several times; each should be a miss
    for i in range(3):
        assert wrapper(i) == i * i
    hits, misses = wrapper.cache_info()
    assert hits == 0
    assert misses == 3

    # Clear should reset miss count
    wrapper.cache_clear()
    hits_cleared, misses_cleared = wrapper.cache_info()
    assert hits_cleared == 0
    assert misses_cleared == 0


def test_wrapper_attribute_exposure():
    """All wrappers should expose the expected attributes."""
    lock = threading.Lock()
    cond = threading.Condition()
    cache = {}
    # Wrapper with both lock and condition, and info
    wrapper = cached._wrapper(
        func=lambda x: x,
        cache=cache,
        key=simple_key,
        lock=lock,
        cond=cond,
        info=info_tuple,
    )
    # Standard function attributes
    assert isinstance(wrapper, types.FunctionType)
    assert wrapper.__name__ == "wrapper"
    # Cached attributes
    assert wrapper.cache is cache
    assert wrapper.cache_key is simple_key
    assert wrapper.cache_lock is lock
    assert wrapper.cache_condition is cond
    # Info attributes
    assert callable(wrapper.cache_info)
    # Clear should not raise
    wrapper.cache_clear()
