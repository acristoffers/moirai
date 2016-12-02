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
import base64
import hashlib
import json
import random
import socket
import string


@decorate_all_methods(dont_raise)
@decorate_all_methods(log)
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
            ret = method(args)
            if ret:
                self.handler.tcp_send(cmd.upper(), ret)

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
        if spass == pswd:
            print('New login from %s' % handler.client_addr)
            handler.authed = True
            return ['OK']
        else:
            print('%s failed to login' % handler.client_addr)
            handler.tcp_send('AUTH', ['FAIL'])
            handler.socket_client = None
            handler.authed = False

    def changepswd(self, args):
        handler = self.handler
        if handler.authed:
            p = args[0]
            handler.send_command('database', 'settings_set', ('password', p))
            return ['OK']
        else:
            return ['FAIL']

    def gensalt(self, args):
        handler = self.handler
        chars = string.ascii_letters + string.digits
        salt = ''.join(random.choice(chars) for _ in range(512))
        salt = bytes(salt, 'utf-8')
        self.salt = salt
        return [salt]

    def hw_list_drivers(self, args):
        handler = self.handler
        handler.send_command('io_manager', 'list_drivers', None)

    def hw_driver_has_setup(self, args):
        handler = self.handler
        handler.send_command('io_manager', 'driver_has_setup', args[0])

    def hw_driver_setup_args(self, args):
        handler = self.handler
        handler.send_command('io_manager', 'driver_setup_arguments', args[0])

    def hw_driver_name_set(self, args):
        handler = self.handler
        handler.send_command('io_manager', 'driver_name_set', args[0])

    def hw_driver_name_get(self, args):
        handler = self.handler
        handler.send_command('io_manager', 'driver_name_get', None)

    def hw_driver_setup_args_values_set(self, args):
        handler = self.handler
        cmd = 'driver_setup_arguments_values_set'
        values = json.loads(args[0])
        handler.send_command('io_manager', cmd, values)

    def hw_driver_setup_args_values_get(self, args):
        handler = self.handler
        cmd = 'driver_setup_arguments_values_get'
        handler.send_command('io_manager', cmd, None)

    def hw_driver_connect(self, args):
        handler = self.handler
        handler.send_command('io_manager', 'hw_connect', None)

    def hw_driver_is_connected(self, args):
        handler = self.handler
        handler.send_command('io_manager', 'is_connected', None)

    def hw_driver_list_ports(self, args):
        handler = self.handler
        handler.send_command('io_manager', 'list_ports', None)

    def hw_port_mapping_set(self, args):
        handler = self.handler
        mappings = [json.loads(port) for port in args]
        handler.send_command('database', 'mappings_set', mappings)
        __, status = handler.read_pipe('database', blocking=True)
        if status == 'OK':
            handler.send_command('io_manager', 'config_ports', None)
            return 'OK'
        return 'ERROR'

    def hw_port_mapping_get(self, args):
        handler = self.handler
        handler.send_command('database', 'mappings_get', None)
        __, ms = handler.read_pipe('database', blocking=True)
        return [json.dumps(m) for m in ms]

    def quit(self, args):
        handler = self.handler
        if handler.authed:
            handler.send_command('parent', 'quit', None)
