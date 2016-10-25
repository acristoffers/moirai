#!/usr/bin/env python3
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

from multiprocessing import Pipe
import time


class AbstractProcessHandler(object):

    def __init__(self, name, pipe):
        print('Starting %s...' % name)
        self._last_message = time.time() + 60
        self._pipes = {}
        self._pname = name  # Printable name
        self.sleep = True
        self.set_pipe('parent', pipe)

    def set_sleep(boole):
        self.sleep = boole

    def pipe_for(self, name):
        return self._pipes.get(name, None)

    def set_pipe(self, name, pipe):
        if pipe:
            self._pipes[name] = pipe
        else:
            del self._pipes[name]

    def pipes(self):
        return list(self._pipes)

    def send_command(self, to, cmd, args):
        pipe = self.pipe_for(to)
        pipe.send((cmd, args))

    def read_pipe(self, name, blocking=False):
        pipe = self.pipe_for(name)
        try:
            if blocking or (not blocking and pipe.poll()):
                self._last_message = time.time()
                return pipe.recv()
            else:
                return (None, None)
        except EOFError:
            sname = self._pname
            print('Communication between %s and %s is closed!' % (name, sname))
            return (None, None)

    def _process_command(self, name):
        cmd, args = self.read_pipe(name)
        if cmd == 'quit':
            self.send_command(name, 'ok', None)
            return 'quit'
        elif cmd == 'close':
            pipe.send(('ok', None))
            self.set_pipe(name, None)
            if not self.pipes():
                return 'quit'
        elif cmd == 'connect':
            print('Connected %s to %s' % (args[0], self._pname))
            self.set_pipe(*args)
            self.send_command(name, 'ok', None)
        else:
            self.process_command(name, cmd, args)

    def request_connection(self, pkg_from, pkg_to):
        self.send_command('parent', 'connect', (pkg_from, pkg_to))
        answer, pipe = self.read_pipe('parent', blocking=True)
        if answer == 'ok':
            self.set_pipe(pkg_to, pipe)
        else:
            raise RuntimeError('Cannot connect with %s' % pkg_to)

    def run(self):
        while True:
            if self.sleep and time.time() - self._last_message > 1:
                time.sleep(1)
            for name in self.pipes():
                result = self._process_command(name)
                if result == 'quit':
                    print('Shutting down %s...' % self._pname)
                    self.quit()
                    for name in self.pipes():
                        self.set_pipe(name, None)
                    return
            self.loop()
