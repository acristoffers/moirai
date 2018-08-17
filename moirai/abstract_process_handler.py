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

import time


class AbstractProcessHandler(object):
    """
    Base class for modules ProcessHandlers. Defines the API used by two
    processes to communicate and execute code asynchronously.
    """

    def __init__(self, name, pipe):
        print('Starting %s...' % name)
        self._last_message = time.time() + 60
        self._pipes = {}
        self._pname = name  # Printable name
        self.sleep = True
        self.quitting = False
        self.set_pipe('parent', pipe)

    def set_sleep(self, sleep):
        """
        Set's the sleep property.
        """
        self.sleep = sleep

    def pipe_for(self, name):
        """
        Returns the pipe used to communicate with process `name`.
        """
        return self._pipes.get(name, None)

    def set_pipe(self, name, pipe):
        """
        Sets the pipe used to communicate with process `name`.
        """
        if pipe:
            self._pipes[name] = pipe
        else:
            del self._pipes[name]

    def pipes(self):
        """
        Returns a list of all pipes registered.
        """
        return list(self._pipes)

    def send_command(self, destination, cmd, args):
        """
        Sends a command `cmd` to the process named `destination` with
        arguments `args`
        """
        pipe = self.pipe_for(destination)
        if pipe:
            pipe.send((cmd, args))
        else:
            print("No pipe for %s" % destination)

    def read_pipe(self, name, blocking=False):
        """
        Read from pipe `name`.
        """
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
            del self._pipes[name]
            return (None, None)

    def process_command(self, sender, cmd, args):
        """
        Abstract method to be implemented by classes extending this class.
        """
        pass

    def _process_command(self, name):
        cmd, args = self.read_pipe(name)
        if cmd == 'quit':
            self.quitting = True
            self.send_command(name, 'ok', None)
            return 'quit'
        elif cmd == 'close':
            pipe = self.pipe_for(name)
            pipe.send(('ok', None))
            self.set_pipe(name, None)
            if not self.pipes():
                return 'quit'
        elif cmd == 'connect':
            print('Connected %s to %s' % (args[0], self._pname))
            self.set_pipe(*args)
            self.send_command(name, 'ok', None)
        elif cmd == 'alive':
            self.send_command(name, 'alive', None)
        else:
            self.process_command(name, cmd, args)

    def request_connection(self, pkg_from, pkg_to):
        """
        Ask the main process for a pipe with process `pkg_to`.
        """
        self.send_command('parent', 'connect', (pkg_from, pkg_to))
        answer, pipe = self.read_pipe('parent', blocking=True)
        if answer == 'ok':
            self.set_pipe(pkg_to, pipe)
        else:
            raise RuntimeError(
                'Can not connect %s with %s' % (pkg_from, pkg_to))

    def loop(self):
        """
        Main loop of the process, to be implemented by the class that inherits
        this class.
        """
        pass

    def run(self):
        """
        Run loop of this process.
        """
        while True:
            if self.sleep and time.time() - self._last_message > 1:
                time.sleep(0.5)
            for name in self.pipes():
                result = self._process_command(name)
                if result == 'quit':
                    print('Shutting down %s...' % self._pname)
                    self.quit()
                    for name2 in self.pipes():
                        self.set_pipe(name2, None)
                    return
            self.loop()

    def quit(self):
        """
        Cleaning code before quitting.
        """
        pass
