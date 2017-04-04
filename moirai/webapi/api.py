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

import hashlib
import json

from flask import Flask, request
from moirai.database import DatabaseV1
from moirai.decorators import decorate_all_methods, dont_raise, log


class APIv1:
    def __init__(self):
        self.app = Flask(__name__)
        self.db = DatabaseV1()

    def run(self):
        self.app.add_url_rule('/', view_func=self.index)
        self.app.add_url_rule('/login', view_func=self.login, methods=['POST'])
        self.app.run(host="0.0.0.0")

    def index(self):
        return 'Moirai Control System\n'

    def login(self):
        """
        Authenticates the user.
        Should be called with a POST request containing the following body:

        {
            "password": "..."
        }

        @returns:
            On success, HTTP 200 Ok and body:

            {
                "token": "..."
            }

            On failure, HTTP 403 Unauthorized and body:

            {
            }
        """
        password = request.json.get('password', '')
        hasher = hashlib.sha512()
        hasher.update(bytes(password, 'utf-8'))
        password = hasher.hexdigest()
        saved_password = self.db.get_setting('password')
        if saved_password == password:
            return json.dumps({'token': self.db.generate_token()})
        else:
            return '{}', 403
