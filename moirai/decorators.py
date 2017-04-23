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

import errno
import inspect
import os
import socket
import time

import appdirs

import moirai

LOG_DIR = appdirs.user_log_dir(appname=moirai.__name__,
                               appauthor=moirai.__author__,
                               version=moirai.__version__)
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = open(os.path.join(LOG_DIR, 'moirai.log'), 'at')


def log_file_path():
    """
    Returns the path of the log file.
    """
    return os.path.join(LOG_DIR, 'moirai.log')


def decorate_all_methods(decorator):
    """
    Decorates every member of a class.
    """
    def decorate(cls):
        """
        Decorates every member of a class.
        """
        for name, func in inspect.getmembers(cls, inspect.isfunction):
            setattr(cls, name, decorator(func))
        return cls
    return decorate


def ignore_eagain(func):
    """
    errno.EAGAIN is generated in some platforms when the socket is
    non-blocking. This decorator ignores this exception, as it's not an error.
    """
    def decorate(ret, *kargs):
        """
        Decorator.
        """
        try:
            return func(*kargs)
        except socket.error as error:
            if error.errno == errno.EAGAIN:
                return ret
            else:
                raise error
    return decorate


def log_msg(msg):
    """
    Logs `msg` to log file.
    """
    msg = '%s: %s\n' % (time.ctime(), msg)
    LOG_FILE.write(msg)
    LOG_FILE.flush()


def log(func):
    """
    Logs every call to a class method.
    """
    def decorate(*kargs, **kwargs):
        """
        Logs every call to a class method.
        """
        func_name = []
        if func.__module__ != '__main__':
            func_name.append(func.__module__)
        func_name.append(func.__qualname__)
        func_name = '.'.join(func_name)

        args = []
        if kargs:
            args = [str(arg) for arg in kargs]
        if kwargs:
            args += ['%s=%s' % i for i in kwargs.items()]
        args = ', '.join(args)

        log_str = '%s(%s)' % (func_name, args)
        log_msg(log_str)
        return func(*kargs, **kwargs)
    return decorate


def dont_raise(func):
    """
    Decorate every member of a class to stop raising exceptions.
    """
    def decorate(*kargs, **kwargs):
        """
        Decorate every member of a class to stop raising exceptions.
        """
        try:
            return func(*kargs, **kwargs)
        except Exception as error:
            log_msg('An Exception occurred: %s' % error)
            print('An Exception occurred: %s' % error)
    return decorate
