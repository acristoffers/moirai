"""
Tests for moirai/decorators.py.

Covers: dont_raise, log, decorate_all_methods, ignore_eagain.
"""

import errno
import socket

import pytest

from moirai.decorators import (
    decorate_all_methods,
    dont_raise,
    ignore_eagain,
    log,
)


# ---------------------------------------------------------------------------
# dont_raise
# ---------------------------------------------------------------------------


class TestDontRaise:
    def test_normal_return_value_preserved(self):
        @dont_raise
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_exception_is_suppressed(self):
        @dont_raise
        def boom():
            raise ValueError("kaboom")

        assert boom() is None

    def test_keyboard_interrupt_propagates(self):
        """KeyboardInterrupt is not an Exception subclass — must not be caught."""
        @dont_raise
        def interrupt():
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            interrupt()

    def test_works_on_methods(self):
        class MyClass:
            @dont_raise
            def risky(self):
                raise RuntimeError("oops")

        assert MyClass().risky() is None


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------


class TestLog:
    def test_return_value_preserved(self):
        @log
        def mul(a, b):
            return a * b

        assert mul(3, 4) == 12

    def test_kwargs_return_preserved(self):
        @log
        def greet(name="world"):
            return f"Hello, {name}!"

        assert greet(name="Alice") == "Hello, Alice!"

    def test_none_return_preserved(self):
        @log
        def nothing():
            pass

        assert nothing() is None

    def test_exception_propagates(self):
        @log
        def fail():
            raise TypeError("bad type")

        with pytest.raises(TypeError):
            fail()


# ---------------------------------------------------------------------------
# decorate_all_methods
# ---------------------------------------------------------------------------


class TestDecorateAllMethods:
    def test_all_methods_decorated(self):
        calls = []

        def record(func):
            def wrapper(*a, **kw):
                calls.append(func.__name__)
                return func(*a, **kw)
            return wrapper

        @decorate_all_methods(record)
        class Foo:
            def alpha(self):
                return 1

            def beta(self):
                return 2

        foo = Foo()
        foo.alpha()
        foo.beta()
        assert "alpha" in calls
        assert "beta" in calls

    def test_return_values_still_work(self):
        @decorate_all_methods(dont_raise)
        class Safe:
            def value(self):
                return 42

            def boom(self):
                raise Exception("nope")

        s = Safe()
        assert s.value() == 42
        assert s.boom() is None


# ---------------------------------------------------------------------------
# ignore_eagain
#
# The decorator wraps as: decorate(ret, *kargs) where `ret` is the
# "return value on EAGAIN" passed as the first positional arg on every call,
# and *kargs are forwarded to the original function.
# Example: @ignore_eagain / def read(buf_size): ... / read(b"", 1024)
# ---------------------------------------------------------------------------


class TestIgnoreEagain:
    def test_normal_return_preserved(self):
        @ignore_eagain
        def get_data(size):
            return b"hello"

        # First arg (b"") is the EAGAIN default; 1024 is forwarded to get_data
        assert get_data(b"", 1024) == b"hello"

    def test_eagain_returns_default(self):
        @ignore_eagain
        def nodata():
            err = socket.error("resource unavailable")
            err.errno = errno.EAGAIN
            raise err

        # b"" is the default; no real args forwarded
        assert nodata(b"") == b""

    def test_other_socket_error_propagates(self):
        @ignore_eagain
        def bad():
            err = socket.error("connection reset")
            err.errno = errno.ECONNRESET
            raise err

        with pytest.raises(socket.error):
            bad(None)

    def test_non_socket_exception_propagates(self):
        @ignore_eagain
        def broken():
            raise ValueError("not a socket error")

        with pytest.raises(ValueError):
            broken(None)

