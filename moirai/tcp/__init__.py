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

from moirai.abstract_process_handler import AbstractProcessHandler
from multiprocessing import Pipe
import base64
import errno
import hashlib
import random
import socket
import string


def main(pipe):
    handler = ProcessHandler(pipe)
    handler.run()


def ignore_eagain(f):
    def g(ret, *kargs):
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
        self.tcp_processor = TCPProcessor(self)
        self.socket_client = None
        self.socket_server = None
        self.authed = False
        self._data = ''
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
        if cmd == 'init':
            self.request_connection('tcp', 'database')
            self.request_connection('tcp', 'websocket')
            self.socket_server = socket.socket()
            self.socket_server.bind(('0.0.0.0', 5000))
            self.socket_server.listen()
            self.socket_server.setblocking(False)
            self.send_command('websocket', 'start', None)

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

    def tcp_send(self, cmd, args):
        def b(o):
            if type(o) == str:
                return bytes(o, 'utf-8')
            else:
                return bytes(o)
        b64e = base64.encodebytes
        args = [str(b64e(b(arg)).strip(), 'utf-8') for arg in args]
        cmd = ("%s %s" % (cmd, ' '.join(args))).strip() + ';'
        self.socket_client.send(bytes(cmd, 'utf-8'))

    def loop(self):
        if not self.socket_client and self.socket_server:
            conn, __ = ignore_eagain(self.socket_server.accept)((None, None))
            if conn:
                self.socket_client = conn
        if self.socket_client:
            try:
                self.tcp_send('ALIVE', [])
            except:
                print('Can not send. Closing TCP socket.')
                self.socket_client = None
                self.authed = False
                return
            data = ignore_eagain(self.socket_client.recv)(b'', 4096)
            if len(data) > 0:
                try:
                    self.process_tcp_command(data)
                except Exception as e:
                    print('Exception: %s' % e)


class TCPProcessor(object):

    def __init__(self, handler):
        self.handler = handler
        self.salt = None

    def process_command(self, cmd, args):
        cmd = cmd.lower().strip()
        args = [arg.strip() for arg in args]
        args = [base64.decodebytes(bytes(arg, 'utf-8')) for arg in args]
        args = [str(arg, 'utf-8').strip() for arg in args]
        method = getattr(self, cmd, None)
        if method:
            method(args)

    def auth(self, args):
        handler = self.handler
        pswd = None
        if len(args) > 0:
            pswd = args[0].lower()
        handler.send_command('database', 'settings_get', 'password')
        cmd, spass = handler.read_pipe('database', blocking=True)
        if spass:
            sha512 = hashlib.sha512()
            sha512.update(bytes(spass, 'utf-8') + self.salt)
            spass = sha512.hexdigest().lower().strip()
        try:
            if spass == pswd:
                handler.tcp_send('AUTH', ['OK'])
                handler.authed = True
            else:
                handler.tcp_send('AUTH', ['FAIL'])
                handler.socket_client = None
                handler.authed = False
        except:
            print('Can not send. Closing TCP socket.')
            handler.socket_client = None
            handler.authed = False

    def changepswd(self, args):
        handler = self.handler
        if handler.authed:
            p = args[0]
            handler.send_command('database', 'settings_set', ('password', p))
            handler.tcp_send('CHANGEPSWD', ['OK'])
        else:
            handler.tcp_send('CHANGEPSWD', ['FAIL'])

    def gensalt(self, args):
        handler = self.handler
        chars = string.ascii_letters + string.digits
        salt = ''.join(random.choice(chars) for _ in range(512))
        salt = bytes(salt, 'utf-8')
        self.salt = salt
        handler.tcp_send('GENSALT', [salt])

    def quit(self, args):
        handler = self.handler
        if handler.authed:
            handler.send_command('parent', 'quit', None)
