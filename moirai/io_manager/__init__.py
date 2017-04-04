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

import ahio
from moirai.abstract_process_handler import AbstractProcessHandler
from moirai.decorators import decorate_all_methods, dont_raise, log
from moirai.io_manager.cmd_processor import CommandProcessor
from moirai.io_manager.hardware_layer import HardwareLayer


def main(pipe):
    handler = ProcessHandler(pipe)
    handler.run()


@decorate_all_methods(dont_raise)
class ProcessHandler(AbstractProcessHandler):

    def __init__(self, pipe):
        self.cmd_processor = CommandProcessor(self)
        super().__init__('I/O Manager', pipe)

    def quit(self):
        pass

    def process_command(self, sender, cmd, args):
        if cmd:
            self.cmd_processor.process_command(sender, cmd, args)

    def loop(self):
        pass
