# -*- coding: utf-8; -*-
#
# Copyright (c) 2016 Álan Crístoffer
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import appdirs
import errno
import inspect
import moirai
import os
import socket
import time

log_dir = appdirs.user_log_dir(appname=moirai.__name__,
                               appauthor=moirai.__author__,
                               version=moirai.__version__)
os.makedirs(log_dir, exist_ok=True)
log_file = open(os.path.join(log_dir, 'moirai.log'), 'at')


def log_file_path():
    return os.path.join(log_dir, 'moirai.log')


def decorate_all_methods(decorator):
    def decorate(cls):
        for name, fn in inspect.getmembers(cls, inspect.isfunction):
            setattr(cls, name, decorator(fn))
        return cls
    return decorate


def ignore_eagain(f):
    """
    errno.EAGAIN is generated in some platforms when the socket is
    non-blocking. This decorator ignores this exception, as it's not an error.
    """
    def g(ret, *kargs):
        try:
            return f(*kargs)
        except socket.error as e:
            if e.errno == errno.EAGAIN:
                return ret
            else:
                raise e
    return g


def log_msg(msg):
    msg = '%s: %s\n' % (time.ctime(), msg)
    log_file.write(msg)
    log_file.flush()


def log(f):
    def g(*kargs, **kwargs):
        func_name = []
        if f.__module__ != '__main__':
            func_name.append(f.__module__)
        func_name.append(f.__qualname__)
        func_name = '.'.join(func_name)

        args = []
        if kargs:
            args = [str(arg) for arg in kargs]
        if kwargs:
            args += ['%s=%s' % i for i in a.items()]
        args = ', '.join(args)

        log_str = '%s(%s)' % (func_name, args)
        log_msg(log_str)
        return f(*kargs, **kwargs)
    return g


def dont_raise(f):
    def g(*kargs, **kwargs):
        try:
            return f(*kargs, **kwargs)
        except Exception as e:
            log_msg('An Exception occurred: %s' % e)
            print('An Exception occurred: %s' % e)
    return g
