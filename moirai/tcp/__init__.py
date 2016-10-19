#!/usr/bin/env python3
# -*- cmoiraig: utf-8; -*-
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

from moirai.abstract_process_handler import AbstractProcessHandler
from multiprocessing import Pipe


def main(pipe):
    handler = ProcessHandler(pipe)
    handler.run()


def ignore_eagain(f):
    def g(ret, *kargs):
        import errno
        import socket
        try:
            return f(*kargs)
        except socket.error as e:
            if e.errno == errno.EAGAIN:
                return ret
            else:
                raise e
    return g


class ProcessHandler(AbstractProcessHandler):

    def __init__(self, pipe):
        self.socket_client = None
        self.socket_server = None
        self.authed = False
        super().__init__('TCP', pipe)

    def quit(self):
        def ignore(f):
            def g(*args):
                try:
                    f(*args)
                except:
                    pass
            return g
        import socket
        if self.socket_client:
            ignore(self.socket_client.shutdown)(socket.SHUT_RDWR)
            self.socket_client.close()
            self.socket_client = None
        if self.socket_server:
            ignore(self.socket_server.shutdown)(socket.SHUT_RDWR)
            self.socket_server.close()
            self.socket_server = None

    def process_command(self, sender, cmd, args):
        if cmd == 'init':
            self.request_connection('tcp', 'database')
            import socket
            self.socket_server = socket.socket()
            self.socket_server.bind(('0.0.0.0', 5000))
            self.socket_server.listen()
            self.socket_server.setblocking(False)

    def process_tcp_command(self, raw):
        raw = str(raw, 'utf-8')
        cmd, *args = [arg.strip() for arg in raw.split(' ')]
        cmd = cmd.upper().strip()
        if cmd == 'AUTH':
            from base64 import decodebytes
            pswd = None
            if len(args) == 1:
                try:
                    pswd = str(decodebytes(bytes(args[0], 'utf-8')), 'utf-8')
                except:
                    return
            self.send_command('database', 'settings_get', 'password')
            cmd, spass = self.read_pipe('database', blocking=True)
            if spass == pswd:
                self.socket_client.send(b'AUTH OK\n')
                self.authed = True
            else:
                self.socket_client.send(b'AUTH FAIL\n')
                self.socket_client = None
                self.authed = False
        if cmd == 'QUIT':
            if self.authed:
                self.send_command('parent', 'quit', None)

    def loop(self):
        if not self.socket_client and self.socket_server:
            conn, __ = ignore_eagain(self.socket_server.accept)((None, None))
            if conn:
                self.socket_client = conn
        if self.socket_client:
            try:
                self.socket_client.send(b'ALIVE')
            except:
                self.socket_client = None
                self.authed = False
                return
            data = ignore_eagain(self.socket_client.recv)(b'', 4096)
            if len(data) > 0:
                self.process_tcp_command(data)
