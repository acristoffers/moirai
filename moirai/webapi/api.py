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
from enum import Enum

from flask import Flask, request
from moirai.database import DatabaseV1
from moirai.decorators import decorate_all_methods, dont_raise, log
from moirai.hardware import Hardware


class APIv1:
    def __init__(self):
        self.app = Flask(__name__)
        self.db = DatabaseV1()
        self.hw = Hardware()

    def run(self):
        self.app.add_url_rule('/',
                              view_func=self.index)
        self.app.add_url_rule('/login',
                              view_func=self.login,
                              methods=['POST'])
        self.app.add_url_rule('/hardware/drivers',
                              view_func=self.hardware_drivers,
                              methods=['GET'])
        self.app.run(host="0.0.0.0")

    def verify_token(self):
        authorization = request.headers.get('Authorization')
        token = authorization.split(' ')[-1]
        return self.db.verify_token(token)

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

    def hardware_drivers(self):
        if not self.verify_token():
            return '{}', 403
        ds = self.hw.list_drivers()
        ds = [{
            'name': d,
            'has_setup': self.hw.driver_has_setup(d),
            'setup_arguments': self.hw.driver_setup_arguments(d),
            'ports': self.ports_for_driver(d)
        } for d in ds]
        return json.dumps(ds)

    def ports_for_driver(self, driver):
        ps = self.hw.driver_ports(driver)
        ps = [self.encode_port(p) for p in ps]
        return ps

    def encode_port(self, port):
        """
        If the port is a Enum, us its value. If it's a value that can be dumped
        to JSON, use it, if not, raise an exception.
        """
        port_id = port['id']
        if isinstance(port['id'], Enum):
            port_id = port['id'].value
        else:
            try:
                port_id = json.dumps(port['id'])
            except:
                pass
        port['id'] = port_id
        return port

    def decode_port(self, driver, port):
        """
        If the ID in port should be converted to Enum, do it. Else, keep it as
        it is.
        """
        if driver not in ahio.list_available_drivers():
            return port
        driver = ahio.new_driver(driver)
        ps = driver.available_pins()
        if len(ps) > 0:
            p = ps[0]
            if isinstance(p['id'], Enum):
                port['id'] = p['id'].__class__(port['id'])
        return port
