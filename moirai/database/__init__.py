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

from multiprocessing import Pipe
from moirai.abstract_process_handler import AbstractProcessHandler
from moirai.database.models.setting import Settings
import os
import moirai.database.db
import orator


def main(pipe):
    # Updates database
    db_conf_path = os.path.join(os.path.dirname(__file__), 'db.py')
    os.system("orator -n -q migrate -c %s" % db_conf_path)
    # Initializes module
    orator.Model.set_connection_resolver(moirai.database.db.db)
    handler = ProcessHandler(pipe)
    handler.run()


class ProcessHandler(AbstractProcessHandler):

    def __init__(self, pipe):
        super().__init__('Database', pipe)

    def quit(self):
        pass

    def process_command(self, sender, cmd, args):
        if cmd == 'settings_set':
            key, value = args
            Settings.set(key, value)
            self.send_command(sender, 'ok', None)
        elif cmd == 'settings_get':
            key = args
            value = Settings.get(key)
            self.send_command(sender, 'ok', value)

    def loop(self):
        pass
