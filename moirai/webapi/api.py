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
from moirai.hardware import Hardware


class APIv1:
    """
    Starts a WebServer for the API endpoint.
    """

    def __init__(self):
        self.app = Flask(__name__)
        self.database = DatabaseV1()
        self.hardware = Hardware()

    def run(self):
        """
        Entry point for the class. Adds routes and starts listening.
        """
        self.app.add_url_rule('/',
                              view_func=lambda: 'Moirai Control System\n')
        self.app.add_url_rule('/login',
                              view_func=self.login,
                              methods=['POST'])
        self.app.add_url_rule('/hardware/drivers',
                              view_func=self.hardware_drivers,
                              methods=['GET'])
        self.app.add_url_rule('/hardware/configuration',
                              view_func=self.hardware_set_configuration,
                              methods=['POST'])
        self.app.add_url_rule('/hardware/configuration',
                              view_func=self.hardware_get_configuration,
                              methods=['GET'])
        self.app.run(host="0.0.0.0")

    def verify_token(self):
        """
        Verifies the token sent as a HTTP Authorization header.
        """
        authorization = request.headers.get('Authorization')
        token = authorization.split(' ')[-1]
        return self.database.verify_token(token)

    def login(self):
        """
        Authenticates the user.
        Should be called with a POST request containing the following body:

        {
            "password": string
        }

        @returns:
            On success, HTTP 200 Ok and body:

            {
                "token": string
            }

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        password = request.json.get('password', '')
        hasher = hashlib.sha512()
        hasher.update(bytes(password, 'utf-8'))
        password = hasher.hexdigest()
        saved_password = self.database.get_setting('password')
        if saved_password == password:
            return json.dumps({'token': self.database.generate_token()})
        return '{}', 403

    def hardware_drivers(self):
        """
        Returns a JSON object with all the available drivers, their setups, if
        any, and ports, if listable.

        @returns:
            {
                name: string,
                has_setup: boolean,
                setup_arguments: [
                    {
                        name: string,
                        default_value: string
                    }
                ],
                ports: [
                    {
                        id: number,
                        name: string,
                        analog: {
                            input: boolean,
                            output: boolean,
                            read_range: [number, number],
                            write_range: [number, number]
                        }
                        digital: {
                            input: boolean,
                            output: boolean,
                            pwm: boolean
                        }
                    }
                ]
            }
        """
        if not self.verify_token():
            return '{}', 403
        drivers = self.hardware.list_drivers()
        drivers = [{
            'name': driver,
            'has_setup': self.hardware.driver_has_setup(driver),
            'setup_arguments': self.hardware.driver_setup_arguments(driver),
            'ports': self.ports_for_driver(driver)
        } for driver in drivers]
        return json.dumps(drivers)

    def hardware_set_configuration(self):
        """
        Saves the given driver configuration. It must be a POST request with
        the following body:

        {
            name: string,
            setup_arguments: [
                {
                    name: string,
                    value: string
                }
            ],
            ports: [
                {
                    id: number,
                    name: string | number,
                    alias: string,
                    type: number,
                    defaultValue: string
                }
            ]
        }

        @returns:
            On success, HTTP 200 Ok and body:

            {}

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403
        configuration = request.json
        self.database.set_setting('hardware_configuration', configuration)
        return '{}'

    def hardware_get_configuration(self):
        """
        Returns the saved driver configuration. It must be a GET request.

        @returns:
            On success, HTTP 200 Ok and body:

            {
                name: string,
                setup_arguments: [
                    {
                        name: string,
                        value: string
                    }
                ],
                ports: [
                    {
                        id: number,
                        name: string | number,
                        alias: string,
                        type: number,
                        defaultValue: string
                    }
                ]
            }

            or

            {} if there is no configuration saved

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        configuration = self.database.get_setting('hardware_configuration')
        if configuration is not None:
            return json.dumps(configuration)
        return '{}'

    def ports_for_driver(self, driver):
        """
        Returns a list of encoded ports for the given driver.
        """
        ps = self.hardware.driver_ports(driver)
        ps = [self.encode_port(p) for p in ps]
        return ps

    def encode_port(self, port):
        """
        If the port is a Enum, use its value. If it's a value that can be dumped
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
