import threading
import types
import pytest
from cachetools import _cached


def identity_key(*args, **kwargs):
    """Simple key function that returns the first positional argument."""
    return args[0] if args else None


def info_func(hits, misses):
    """Info function that returns a tuple of hits and misses."""
    return hits, misses


def test_uncached_wrapper_calls_function_and_has_no_info():
    """_wrapper with no cache and no info should behave like a plain function."""
    calls = []

    def func(x):
        calls.append(x)
        return x * 2

    wrapper = _cached._wrapper(func, cache=None, key=identity_key)
    assert wrapper(3) == 6
    assert calls == [3]
    # No info support
    assert wrapper.cache_info is None
    # Attribute exposure
    assert wrapper.cache is None
    assert wrapper.cache_key is identity_key
    assert wrapper.cache_lock is None
    assert wrapper.cache_condition is None
    # Preserve metadata
    assert wrapper.__name__ == func.__name__
    assert wrapper.__doc__ == func.__doc__


def test_uncached_info_counts_misses_and_clears():
    """_uncached_info should count calls as misses and reset on clear."""
    calls = []

    def func(x):
        calls.append(x)
        return x + 1

    wrapper = _cached._wrapper(func, cache=None, key=identity_key, info=info_func)
    # No caching, each call is a miss
    assert wrapper(1) == 2
    assert wrapper(2) == 3
    assert wrapper.cache_info() == (0, 2)  # hits always 0
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)


def test_locked_wrapper_caches_and_counts_hits_and_misses():
    """_locked_info should cache results and count hits/misses correctly."""
    cache = {}
    lock = threading.Lock()
    calls = []

    def func(x):
        calls.append(x)
        return x * x

    wrapper = _cached._wrapper(
        func, cache=cache, key=identity_key, lock=lock, info=info_func
    )
    # First call: miss, compute and store
    assert wrapper(2) == 4
    assert wrapper.cache_info() == (0, 1)
    # Second call with same key: hit
    assert wrapper(2) == 4
    assert wrapper.cache_info() == (1, 1)
    # Different key: miss
    assert wrapper(3) == 9
    assert wrapper.cache_info() == (1, 2)
    # Clear cache and stats
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    # Ensure underlying cache was cleared
    assert cache == {}


def test_condition_wrapper_blocks_and_caches():
    """_condition should block concurrent calls for the same key until the first finishes."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    start_event = threading.Event()
    continue_event = threading.Event()
    results = {}

    def func(x):
        # Signal that the function has started for the first caller
        if not start_event.is_set():
            start_event.set()
            # Wait until test allows continuation
            continue_event.wait()
        return x * 10

    wrapper = _cached._wrapper(
        func, cache=cache, key=identity_key, lock=lock, cond=cond
    )

    def call_wrapper(val):
        results[val] = wrapper(val)

    # First thread starts computation
    t1 = threading.Thread(target=call_wrapper, args=(5,))
    t1.start()
    # Wait until the first call has entered the function
    start_event.wait(timeout=1)
    # Second thread attempts same key; should block
    t2 = threading.Thread(target=call_wrapper, args=(5,))
    t2.start()
    # Give a moment for t2 to attempt to acquire; it should not have completed yet
    threading.Event().wait(0.01)
    assert 5 not in results  # second call hasn't finished
    # Allow first call to finish
    continue_event.set()
    t1.join()
    t2.join()
    # Both should have the same result and cache should contain the key
    assert results[5] == 50
    assert cache[5] == 50
    # Subsequent call should be a cache hit (no blocking)
    assert wrapper(5) == 50


def test_condition_info_counts_and_clears():
    """_condition_info should count hits/misses and support clearing."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x + 5

    wrapper = _cached._wrapper(
        func, cache=cache, key=identity_key, lock=lock, cond=cond, info=info_func
    )
    # First call: miss
    assert wrapper(1) == 6
    assert wrapper.cache_info() == (0, 1)
    # Second call: hit
    assert wrapper(1) == 6
    assert wrapper.cache_info() == (1, 1)
    # Clear stats and cache
    wrapper.cache_clear()
    assert wrapper.cache_info() == (0, 0)
    assert cache == {}
    # After clear, another call is a miss again
    assert wrapper(1) == 6
    assert wrapper.cache_info() == (0, 1)


def test_wrapper_attribute_exposure():
    """All wrapper attributes should be correctly set for various configurations."""
    lock = threading.Lock()
    cond = threading.Condition(lock)
    cache = {}
    func = lambda x: x

    # No cache, no info
    w1 = _cached._wrapper(func, cache=None, key=identity_key)
    assert w1.cache is None
    assert w1.cache_key is identity_key
    assert w1.cache_lock is None
    assert w1.cache_condition is None
    assert w1.cache_info is None

    # Cache with lock, no info
    w2 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock)
    assert w2.cache is cache
    assert w2.cache_lock is lock
    assert w2.cache_condition is None
    assert w2.cache_info is None

    # Cache with condition and lock, no info
    w3 = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, cond=cond)
    assert w3.cache is cache
    assert w3.cache_lock is lock
    assert w3.cache_condition is cond
    assert w3.cache_info is None

    # Cache with info only
    w4 = _cached._wrapper(func, cache=cache, key=identity_key, info=info_func)
    assert w4.cache is cache
    assert w4.cache_lock is None
    assert w4.cache_condition is None
    assert callable(w4.cache_info)


def test_unlocked_wrapper_without_lock():
    """_unlocked should work when no lock is provided."""
    cache = {}
    calls = []

    def func(x):
        calls.append(x)
        return x * 3

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key)
    # First call: miss, stores result
    assert wrapper(4) == 12
    assert calls == [4]
    assert cache[4] == 12
    # Second call: hit, no additional call
    assert wrapper(4) == 12
    assert calls == [4]
    # Attributes
    assert wrapper.cache_lock is None
    assert wrapper.cache_condition is None


def test_cache_set_raises_value_error():
    """When the underlying cache raises ValueError on set, wrapper should swallow it."""
    class BadCache(dict):
        def __setitem__(self, key, value):
            raise ValueError("value too large")

    cache = BadCache()
    lock = threading.Lock()

    def func(x):
        return x * 2

    wrapper = _cached._wrapper(func, cache=cache, key=identity_key, lock=lock, info=info_func)
    # First call: miss, attempts to store but ValueError is swallowed
    assert wrapper(7) == 14
    # Cache should still be empty because set raised
    assert 7 not in cache
    # Miss count should be recorded
    assert wrapper.cache_info() == (0, 1)


def test_wrapper_preserves_name_and_doc():
    """The wrapper should preserve the original function's __name__ and __doc__."""
    def original(a, b):
        """Add two numbers."""
        return a + b

    wrapper = _cached._wrapper(original, cache=None, key=lambda a, b: (a, b))
    assert wrapper.__name__ == original.__name__
    assert wrapper.__doc__ == original.__doc__
