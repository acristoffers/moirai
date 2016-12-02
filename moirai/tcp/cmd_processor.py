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

from moirai.decorators import decorate_all_methods, dont_raise, ignore_eagain, log
import errno
import json
import socket


@decorate_all_methods(dont_raise)
@decorate_all_methods(log)
class CommandProcessor(object):

    def __init__(self, handler):
        self.handler = handler

    def process_command(self, sender, cmd, args):
        cmd = cmd.lower().strip()
        method = getattr(self, cmd, None)
        if method:
            ret = method(args)
            if ret:
                self.handler.send_command(sender, cmd, ret)

    def init(self, args):
        self.handler.request_connection('tcp', 'io_manager')
        self.handler.request_connection('tcp', 'database')
        self.handler.request_connection('tcp', 'websocket')
        self.handler.socket_server = socket.socket()
        try:
            self.handler.socket_server.bind(('0.0.0.0', 5000))
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:
                print('Address already in use. Quitting.')
            else:
                print('Something happened while connecting. Quitting.')
            self.handler.send_command('parent', 'quit', None)
        self.handler.socket_server.listen()
        self.handler.socket_server.setblocking(False)
        self.handler.send_command('websocket', 'start', None)

    def list_drivers(self, drivers):
        self.handler.tcp_send('HW_LIST_DRIVERS', drivers)

    def driver_has_setup(self, status):
        self.handler.tcp_send('HW_DRIVER_HAS_SETUP', [status])

    def driver_setup_arguments(self, args):
        args = [json.dumps(arg) for arg in args]
        self.handler.tcp_send('HW_DRIVER_SETUP_ARGS', args)

    def driver_name_get(self, args):
        name = args or ''
        self.handler.tcp_send('HW_DRIVER_NAME_GET', [name])

    def driver_setup_arguments_values_get(self, args):
        values = args or '[]'
        values = json.dumps(args)
        self.handler.tcp_send('HW_DRIVER_SETUP_ARGS_VALUES_GET', [values])

    def hw_connect(self, status):
        self.handler.tcp_send('HW_DRIVER_CONNECT', [status])

    def is_connected(self, status):
        self.handler.tcp_send('HW_DRIVER_IS_CONNECTED', [status])

    def list_ports(self, ports):
        ports = [json.dumps(port) for port in ports]
        self.handler.tcp_send('HW_DRIVER_LIST_PORTS', ports)
