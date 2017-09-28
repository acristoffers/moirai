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

from moirai.decorators import decorate_all_methods, dont_raise, log
from moirai.hardware.system_response_tests import SystemResponseTest
from moirai.hardware.controller import Controller


@decorate_all_methods(dont_raise)
@decorate_all_methods(log)
class CommandProcessor(object):
    """
    Processes commands for this process
    """

    def __init__(self, handler):
        self.handler = handler

    def process_command(self, sender, cmd, args):
        """
        Handles commands received from other processes.
        """
        cmd = cmd.lower().strip()
        method = getattr(self, cmd, None)
        if method:
            ret = method(args)
            if ret:
                self.handler.send_command(sender, cmd, ret)

    def init(self, _):
        """
        Initialization function for this process.
        """
        pass

    def run_test(self, test):
        test = SystemResponseTest(test)
        test.run()

    def run_controller(self, controller):
        controller = Controller(controller)
        controller.run()
