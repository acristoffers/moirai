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

import json
from pathlib import Path

__printed = False


def DatabaseV1():
    global __printed
    try:
        with open('%s/.moirai.json' % str(Path.home())) as f:
            cfgstr = f.read()
            if cfgstr:
                cfg = json.loads(cfgstr)
                db = cfg.get('database', None)
                if db:
                    adapter = db.get('adapter', 'mongodb')
                    host = db.get('host', '127.0.0.1')
                    port = db.get('port', 3306)
                    username = db.get('username', None)
                    password = db.get('password', None)
                    if adapter == 'mongodb':
                        if not __printed:
                            print('Using MongoDB')
                            __printed = True
                        from moirai.database.mongodb import DatabaseV1
                        return DatabaseV1()
                    else:
                        if not __printed:
                            print('Using MySQL')
                            __printed = True
                        from moirai.database.mysql import DatabaseV1
                        return DatabaseV1(host, port, username, password)
    except Exception:
        print('Falling back to MongoDB...')
        from moirai.database.mongodb import DatabaseV1
        return DatabaseV1()
