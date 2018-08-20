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

import io
import zipfile
import hashlib
import json
import dateutil.parser
import logging
import os.path
import tempfile
import scipy.io as sio

from bson import json_util
from enum import Enum

from cheroot.wsgi import Server
from cheroot.wsgi import PathInfoDispatcher
from flask import Flask, request, send_file
from werkzeug.serving import WSGIRequestHandler
from moirai.database import DatabaseV1
from moirai.hardware import Hardware


class APIv1:
    """
    Starts a WebServer for the API endpoint.
    """

    def __init__(self, processHandler):
        self.app = Flask(__name__)
        self.database = DatabaseV1()
        self.hardware = Hardware()
        self.ph = processHandler
        logging.getLogger('werkzeug').setLevel(logging.ERROR)

    def run(self):
        """
        Entry point for the class. Adds routes and starts listening.
        """

        @self.app.after_request
        def add_header(response):
            response.headers['Cache-Control'] = 'no-store'
            return response

        self.app.add_url_rule('/', view_func=lambda: 'Moirai Control System\n')
        self.app.add_url_rule('/login', view_func=self.login, methods=['POST'])
        self.app.add_url_rule(
            '/set-password', view_func=self.set_password, methods=['POST'])
        self.app.add_url_rule(
            '/last_error', view_func=self.last_error, methods=['GET'])
        self.app.add_url_rule(
            '/hardware/drivers',
            view_func=self.hardware_drivers,
            methods=['GET'])
        self.app.add_url_rule(
            '/hardware/configuration',
            view_func=self.hardware_set_configuration,
            methods=['POST'])
        self.app.add_url_rule(
            '/hardware/configuration',
            view_func=self.hardware_get_configuration,
            methods=['GET'])
        self.app.add_url_rule(
            '/system_response/tests',
            view_func=self.system_response_get_tests,
            methods=['GET'])
        self.app.add_url_rule(
            '/system_response/tests',
            view_func=self.system_response_set_tests,
            methods=['POST'])
        self.app.add_url_rule(
            '/system_response/test/run',
            view_func=self.system_response_run,
            methods=['POST'])
        self.app.add_url_rule(
            '/system_response/test/stop',
            view_func=self.system_response_stop,
            methods=['GET'])
        self.app.add_url_rule(
            '/live_graph/tests',
            view_func=self.live_graph_list_tests,
            methods=['GET'])
        self.app.add_url_rule(
            '/live_graph/test',
            view_func=self.live_graph_get_test,
            methods=['POST'])
        self.app.add_url_rule(
            '/live_graph/test/remove',
            view_func=self.live_graph_remove_test,
            methods=['POST'])
        self.app.add_url_rule(
            '/live_graph/test/export',
            view_func=self.live_graph_export_mat,
            methods=['POST'])
        self.app.add_url_rule(
            '/controllers', view_func=self.controller_set, methods=['POST'])
        self.app.add_url_rule(
            '/controllers', view_func=self.controller_get, methods=['GET'])
        self.app.add_url_rule(
            '/controllers/run',
            view_func=self.controller_run,
            methods=['POST'])
        self.app.add_url_rule(
            '/controllers/stop',
            view_func=self.controller_stop,
            methods=['GET'])
        self.app.add_url_rule(
            '/dev/gen_dummy_tests',
            view_func=self.dev_gen_dummy_tests,
            methods=['GET'])
        self.app.add_url_rule(
            '/db/dump', view_func=self.dump_database, methods=['GET'])
        self.app.add_url_rule(
            '/db/restore', view_func=self.restore_database, methods=['POST'])

        d = PathInfoDispatcher({'/': self.app})
        self.server = Server(('0.0.0.0', 5000), d)
        self.server.start()

    def stop(self):
        self.server.stop()

    def verify_token(self):
        """
        Verifies the token sent as a HTTP Authorization header.
        """
        try:
            authorization = request.headers.get('Authorization')
            token = authorization.split(' ')[-1]
            return self.database.verify_token(token)
        except Exception as e:
            return False

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

    def set_password(self):
        """
        Sets the password. Required body:

        {
            "password": string
        }

        @returns:
            On success, HTTP 200 Ok and body:

            {}

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403
        password = request.json.get('password', '')
        hasher = hashlib.sha512()
        hasher.update(bytes(password, 'utf-8'))
        password = hasher.hexdigest()
        self.database.set_setting('password', password)
        return '{}'

    def last_error(self):
        """
        Returns the last error in the database.

        @returns:
            {
                message: string
            }
        """
        if not self.verify_token():
            return '{}', 403
        error = self.database.get_setting('test_error')
        return json.dumps({'message': error})

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
            'name':
            driver,
            'has_setup':
            self.hardware.driver_has_setup(driver),
            'setup_arguments':
            self.hardware.driver_setup_arguments(driver),
            'ports':
            self.__ports_for_driver(driver)
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
            ],
            configurations: [
                {
                    port: number,
                    alias: string,
                    formula: string
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
                ],
                configurations: [
                    {
                        port: number,
                        alias: string,
                        formula: string
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

        config = self.database.get_setting('hardware_configuration') or {}
        return json.dumps(config)

    def system_response_get_tests(self):
        """
        Returns the saved system response tests. It must be a GET request.

        @returns:
            On success, HTTP 200 Ok and body:

            [{
                id: number
                name: string
                type: string
                inputs: string[]
                output: string
                points: [{
                    x: number
                    y: number
                }]
                fixedOutputs: [{
                    alias: string
                    value: number
                }]
                logRate: number
            }]

            or

            [] if there is no configuration saved

            On failure, HTTP 403 Unauthorized and body:

            []
        """
        if not self.verify_token():
            return '{}', 403

        tests = self.database.get_setting('system_response_tests') or []
        return json.dumps(tests)

    def system_response_set_tests(self):
        """
        Sets the saved system response tests. It must be a POST request with
        the following body:

        [{
            id: number
            name: string
            type: string
            inputs: string[]
            output: string
            points: [{
                x: number
                y: number
            }]
            fixedOutputs: [{
                alias: string
                value: number
            }]
            logRate: number
        }]

        @returns:
            On success, HTTP 200 Ok and body:

            {}

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        tests = request.json
        self.database.set_setting('system_response_tests', tests)
        return '{}'

    def system_response_run(self):
        """
        Runs the given test. It must be a POST request with the following body:

        {
            test: number
        }

        @returns:
            On success, HTTP 200 Ok and body:

            {}

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        test = request.json['test']
        self.ph.send_command("hardware", "run_test", test)
        return '{}'

    def system_response_stop(self):
        """
        Stops the running test. It must be a GET request.

        @returns:
            On success, HTTP 200 Ok and body:

            {}

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        self.database.set_setting('current_test', None)

        return '{}'

    def live_graph_list_tests(self):
        """
        Returns a list of available graphs. It must be a GET request.

        @returns:
            On success, HTTP 200 Ok and body:

            [
                {
                    name: string
                    date: string (ISO 8601)
                    running: boolean
                }
            ]

            On failure, HTTP 403 Unauthorized and body:

            []
        """
        if not self.verify_token():
            return '{}', 403
        running_test = self.database.get_setting('current_test')
        tests = self.database.list_test_data()

        if len(tests) == 0:
            return '[]'

        last_date = max([test['date'] for test in tests])
        tests = [{
            'name':
            t['name'],
            'date':
            t['date'].isoformat(),
            'running':
            t['name'] == running_test and t['date'] == last_date
        } for t in tests]

        return json.dumps(tests)

    def live_graph_get_test(self):
        """
        Returns a graph. It must be a POST request with following body:

        {
            test: string
            start_time: string (ISO 8601)
            skip?: number
        }

        @returns:
            On success, HTTP 200 Ok and body:

            [
                {
                    sensor: string
                    time: string | number
                    value: string | number
                }
            ]

            On failure, HTTP 403 Unauthorized and body:

            []
        """
        if not self.verify_token():
            return '{}', 403

        test = request.json['test']
        start_time = dateutil.parser.parse(request.json['start_time'])
        skip = request.json.get('skip', 0)

        points = self.database.get_test_data(test, start_time, skip)

        return json.dumps(points)

    def live_graph_remove_test(self):
        """
        Deletes a test. It must be a POST request with following body:

        {
            test: string
            start_time: string (ISO 8601)
        }

        or a list of elements like that.

        @returns:
            On success, HTTP 200 Ok and body:

            []

            On failure, HTTP 403 Unauthorized and body:

            []
        """
        if not self.verify_token():
            return '{}', 403

        ts = request.json
        if isinstance(ts, list):
            ts = [{
                'test': t['test'],
                'start_time': dateutil.parser.parse(t['start_time'])
            } for t in ts]
        else:
            ts = {
                'test': ts['test'],
                'start_time': dateutil.parser.parse(ts['start_time'])
            }

        self.database.remove_test(ts)

        return '[]'

    def live_graph_export_mat(self):
        """
        Generates a MATLAB's MAT file from data. It must be a POST request with
        following body:

        {
            test: string
            start_time: string (ISO 8601)
        }

        @returns:
            On success, HTTP 200 Ok and body:

            file-contents

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        test = request.json['test']
        start_time = dateutil.parser.parse(request.json['start_time'])
        v = request.json['variables']

        ks = list(v.keys())
        ds = self.database.get_filtered_test_data(test, start_time, ks)
        ts = ds[0]['time']
        ds = {d['sensor']: d['values'] for d in ds}
        ds['t'] = ts

        directory = tempfile.gettempdir()
        file_path = os.path.join(directory, 'test.mat')

        sio.savemat(file_path, ds)

        f = open(file_path, 'rb')

        return send_file(f, as_attachment=True, attachment_filename='data.mat')

    def controller_set(self):
        """
        Saves a controller. It must be a POST request with following body:

        [{
            id: number
            name: string
            tau: number
            runTime: number
            before: string
            controller: string
            after: string
            inputs: string[]
        }]

        @returns:
            On success, HTTP 200 Ok and body:

            {}

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        cs = request.json
        self.database.set_setting('controllers', cs)
        return '{}'

    def controller_get(self):
        """
        Get saved controllers. It must be a GET request.

        @returns:
            On success, HTTP 200 Ok and body:

            [{
                id: number
                name: string
                tau: number
                runTime: number
                before: string
                controller: string
                after: string
                inputs: string[]
            }]

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        cs = self.database.get_setting('controllers') or []
        return json.dumps(cs)

    def controller_run(self):
        """
        Runs the given controller. It must be a POST request with the following
        body:

        {
            controller: number
        }

        @returns: On success, HTTP 200 Ok and body:

            {}

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        controller = request.json['controller']
        self.ph.send_command("hardware", "run_controller", controller)
        return '{}'

    def controller_stop(self):
        """
        Stops the running controller. It must be a GET request.

        @returns:
            On success, HTTP 200 Ok and body:

            {}

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        self.database.set_setting('current_test', None)

        return '{}'

    def dump_database(self):
        """
        Dumps the database collections. Use for backup.

        @returns:
            On success, HTTP 200 Ok and body:

            {
                settings: []
                test_sensor_values: []
            }

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403

        settings, test_sensor_values = self.database.dump_database()
        data = {'settings': settings, 'test_sensor_values': test_sensor_values}
        jsondata = json.dumps(data, default=json_util.default)

        del data, settings, test_sensor_values  # release memory

        zbuffer = io.BytesIO()
        with zipfile.ZipFile(zbuffer, "a", zipfile.ZIP_LZMA) as zip_file:
            zip_file.writestr('dump', jsondata)
        zbuffer.seek(0, 0)
        return send_file(
            zbuffer,
            as_attachment=True,
            attachment_filename='dump.zip',
            mimetype="application/octet-stream")

    def restore_database(self):
        """
        Restore the database collections. It must be a POST request with following body:

        [{
            settings: []
            test_sensor_values: []
        }]

        @returns:
            On success, HTTP 200 Ok and body:

            {}

            On failure, HTTP 403 Unauthorized and body:

            {}
        """
        if not self.verify_token():
            return '{}', 403
        db = self.database
        file = tempfile.TemporaryFile()
        file.write(request.files['file'].read())
        file.seek(0)
        with zipfile.ZipFile(file, "r", zipfile.ZIP_LZMA) as zip_file:
            jsondata = zip_file.read('dump')
            d = json.loads(jsondata, object_hook=json_util.object_hook)
            del jsondata
            db.restore_database(d['settings'], d['test_sensor_values'])
        return '{}'

    def __ports_for_driver(self, driver):
        """
        Returns a list of encoded ports for the given driver.
        """
        ps = self.hardware.driver_ports(driver)
        ps = [self.__encode_port(p) for p in ps]
        return ps

    def __encode_port(self, port):
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

    def __decode_port(self, driver, port):
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

    def dev_gen_dummy_tests(self):
        import datetime
        start_time = datetime.datetime.utcnow()
        ts = list(range(600))

        xs = ts
        ys = [x**2 for x in xs]
        zs = [2 * x for x in xs]

        vss = [xs, ys, zs]
        ns = ['x', 'y', 'z']

        for n, vs in zip(ns, vss):
            for x, t in zip(vs, ts):
                self.database.save_test_sensor_value('Dummy', n, x, t,
                                                     start_time)

        return '[]'
