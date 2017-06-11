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
import ahio

from multiprocessing import Pipe
from threading import Thread

from moirai.abstract_process_handler import AbstractProcessHandler
from moirai.decorators import decorate_all_methods, dont_raise
from moirai.hardware.cmd_processor import CommandProcessor


def main(pipe):
    """
    Entry point for this process.
    """
    handler = ProcessHandler(pipe)
    handler.run()


@decorate_all_methods(dont_raise)
class ProcessHandler(AbstractProcessHandler):
    """
    Manages this processes' lifecycle and handles IPC.
    """

    def __init__(self, pipe):
        self.cmd_processor = CommandProcessor(self)
        super().__init__('Hardware', pipe)

    def quit(self):
        pass

    def process_command(self, sender, cmd, args):
        """
        Redirects the commands received to the CommandProcessor class.
        """
        if cmd:
            self.cmd_processor.process_command(sender, cmd, args)

    def loop(self):
        pass


def arguments_of(func):
    """
    @returns the list of arguments of func
    """
    def v(name):
        if ps[name].default == inspect.Parameter.empty:
            return {'name': name}
        else:
            return {'name': name, 'default_value': ps[name].default}
    ps = inspect.signature(func).parameters
    return [v(name) for name in ps]


class Hardware(object):
    def list_drivers(self):
        """
        @returns a list of drivers available in this platform.
        """
        return ahio.list_available_drivers()

    def driver_has_setup(self, driver_name):
        """
        @returns True if the driver has a setup function.
        """
        if driver_name not in ahio.list_available_drivers():
            return False
        with ahio.new_driver(driver_name) as driver:
            return hasattr(driver, 'setup')

    def driver_setup_arguments(self, driver):
        """
        @returns a list of field names and default values, ordered.

            {
                "name": "...",
                ["default_value": any]
            }
        """
        if driver not in ahio.list_available_drivers():
            return None
        with ahio.new_driver(driver) as driver:
            if hasattr(driver, 'setup'):
                return arguments_of(driver.setup)
            else:
                return []

    def driver_ports(self, driver):
        if driver not in ahio.list_available_drivers():
            return []
        driver = ahio.new_driver(driver)
        try:
            return driver.available_pins()
        except:
            return []
