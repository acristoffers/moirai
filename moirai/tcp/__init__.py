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

from moirai.abstract_process_handler import AbstractProcessHandler
from moirai.decorators import decorate_all_methods, dont_raise, ignore_eagain, log
from moirai.tcp.cmd_processor import CommandProcessor
from moirai.tcp.tcp_processor import TCPProcessor
from multiprocessing import Pipe
import base64
import socket
import time


def main(pipe):
    handler = ProcessHandler(pipe)
    handler.run()


@decorate_all_methods(dont_raise)
class ProcessHandler(AbstractProcessHandler):

    def __init__(self, pipe):
        self.tcp_processor = TCPProcessor(self)
        self.cmd_processor = CommandProcessor(self)
        self.socket_client = None
        self.socket_server = None
        self.client_addr = ''
        self.authed = False
        self._data = ''
        self._alive_time = time.time()
        super().__init__('TCP', pipe)

    def quit(self):
        def ignore(f):
            def g(*args):
                try:
                    f(*args)
                except:
                    pass
            return g
        if self.socket_client:
            ignore(self.socket_client.shutdown)(socket.SHUT_RDWR)
            self.socket_client.close()
            self.socket_client = None
        if self.socket_server:
            ignore(self.socket_server.shutdown)(socket.SHUT_RDWR)
            self.socket_server.close()
            self.socket_server = None

    def process_command(self, sender, cmd, args):
        if cmd:
            self.cmd_processor.process_command(sender, cmd, args)

    # Intended to implement any pre-process routine, like cryptography
    def preprocess_tcp_command(self, raw):
        try:
            return str(raw, 'utf-8')
        except:
            return ''

    def process_tcp_command(self, raw):
        raw = self._data + self.preprocess_tcp_command(raw)
        *rs, self._data = raw.split(';')
        for raw in rs:
            cmd, *args = [arg.strip() for arg in raw.split(' ')]
            if len(cmd.strip()) == 0:
                continue
            self.tcp_processor.process_command(cmd, args)

    def tcp_read(self):
        try:
            return ignore_eagain(self.socket_client.recv)(b'', 4096)
        except:
            print('Lost connection with %s' % self.client_addr)
            self.socket_client = None
            self.authed = False
            return b''

    def tcp_send(self, cmd, args):
        if self.socket_client:
            def b(o):
                if type(o) == str:
                    return bytes(o, 'utf-8')
                elif type(o) == bool:
                    return b'true' if o else b'false'
                elif type(o) == int:
                    return bytes(str(o), 'utf-8')
                else:
                    return bytes(o)
            b64e = base64.encodebytes
            args = [str(b64e(b(arg)).strip(), 'utf-8') for arg in args]
            cmd = ("%s %s" % (cmd, ' '.join(args))).strip() + ';'
            try:
                self.socket_client.send(bytes(cmd, 'utf-8'))
                return True
            except:
                print('Lost connection with %s' % self.client_addr)
                self.socket_client = None
                self.authed = False
                return False
        else:
            print('Connection is closed, can not send')
            return False

    def loop(self):
        if not self.socket_client and self.socket_server:
            conn, addr = ignore_eagain(self.socket_server.accept)((None, None))
            if conn:
                self.socket_client = conn
                self.client_addr = addr[0]
        if self.socket_client:
            if time.time() - self._alive_time > 5:
                self._alive_time = time.time()
                if not self.tcp_send('ALIVE', []):
                    return
            data = self.tcp_read()
            if len(data) > 0:
                try:
                    self.process_tcp_command(data)
                except Exception as e:
                    print('Exception: %s' % e)
