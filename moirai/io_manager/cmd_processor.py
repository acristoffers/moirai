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

import inspect
import json

import ahio
from moirai.decorators import decorate_all_methods, dont_raise, log


def arguments_of(func):
    def v(name):
        if ps[name].default == inspect.Parameter.empty:
            return name
        else:
            return (name, ps[name].default)
    ps = inspect.signature(func).parameters
    return [v(name) for name in ps]


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
        self.handler.request_connection('io_manager', 'database')

    def list_drivers(self, args):
        return ahio.list_available_drivers()

    def driver_has_setup(self, args):
        driver_name = args
        if driver_name not in ahio.list_available_drivers():
            print('Asked for non-existent driver %s' % driver_name)
            return
        with ahio.new_driver(driver_name) as driver:
            return hasattr(driver, 'setup')

    def driver_setup_arguments(self, args):
        """Returns a list of field names. If the field is optional and has a
        default argument, it will be a list of name and value. If the field
        has no default value, it's a string.

        Example: ['address', ['port', 3000]]
        """
        driver_name = args
        if driver_name not in ahio.list_available_drivers():
            print('Asked for non-existent driver %s' % driver_name)
            return
        with ahio.new_driver(driver_name) as driver:
            if hasattr(driver, 'setup'):
                return arguments_of(driver.setup)
            else:
                return []

    def driver_name_set(self, args):
        key = 'io_manager_driver_name'
        val = args
        self.handler.send_command('database', 'settings_set', (key, val))

    def driver_name_get(self, __):
        key = 'io_manager_driver_name'
        self.handler.send_command('database', 'settings_get', key)
        __, val = self.handler.read_pipe('database', blocking=True)
        return val

    def driver_setup_arguments_values_set(self, args):
        key = 'io_manager_args_values'
        val = json.dumps(args)
        self.handler.send_command('database', 'settings_set', (key, val))

    def driver_setup_arguments_values_get(self, __):
        """Returns a list of lists of field names and values.

        Example: [['address', 'localhost'], ['port', 3000]]
        """
        key = 'io_manager_args_values'
        self.handler.send_command('database', 'settings_get', key)
        __, val = self.handler.read_pipe('database', blocking=True)
        if val:
            return json.loads(val)

    def hw_connect(self, __):
        driver_name = self.driver_name_get(None)
        if driver_name:
            self.handler.hw.instantiate_driver(driver_name)
            if self.driver_has_setup(driver_name):
                setup_args = self.driver_setup_arguments(driver_name)
                if setup_args:
                    args = self.driver_setup_arguments_values_get(None)
                    if args and len(setup_args) == len(args):
                        args = {k: v for k, v in args}
                        if self.handler.hw.setup(args):
                            return 'OK'
                else:
                    if self.handler.hw.setup():
                        return 'OK'
            else:
                return 'OK'
        return 'FAIL'

    def is_connected(self, __):
        return self.handler.hw.driver != None

    def list_ports(self, __):
        return self.handler.hw.list_ports()

    def config_ports(self, __):
        if not self.is_connected(None):
            return 'FAIL'
        self.handler.send_command('database', 'mappings_get', None)
        __, ports = self.handler.read_pipe('database', blocking=True)
        for port in ports:
            self.handler.hw.config_port(port)
        return 'OK'
