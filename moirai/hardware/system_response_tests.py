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

import ahio
import datetime

from moirai.database import DatabaseV1
from moirai.hardware.configured_hardware import ConfiguredHardware
from moirai.hardware.timer import Timer


class SystemResponseTest(object):
    def __init__(self, test_id):
        self.db = DatabaseV1()
        tests = self.db.get_setting('system_response_tests')
        self.test = next((t for t in tests if t['id'] == test_id), None)
        if self.test is None:
            raise Exception('Test not found')
        self.hardware = ConfiguredHardware()
        configuration = self.db.get_setting('hardware_configuration')
        self.locks = [self.interlock(l) for l in configuration['interlocks']]

    def interlock(self, lock):
        code = compile('y=%s' % lock['expression'], '_string_', 'exec')

        def f(code=code, lock=lock):
            value = self.hardware.read(lock['sensor'])
            scope = {'x': value}
            exec(code, None, scope)
            if scope['y']:
                self.hardware.write(lock['actuator'], lock['actuatorValue'])
                raise Exception('Interlock')
        return f

    def run(self):
        run_time = self.test['points'][-1]['x']
        interval = self.test['logRate']
        t = Timer(run_time, interval)
        port = self.test['output']
        start_time = datetime.datetime.utcnow()
        last_port_value = 0

        self.db.set_setting('current_test', self.test['name'])

        for o in self.test['fixedOutputs']:
            self.hardware.write(o['alias'], o['value'])

        try:
            while self.db.get_setting('current_test') is not None:
                t.sleep()
                t_elapsed = t.elapsed()

                for lock in self.locks:
                    lock()

                for sensor in self.test['inputs']:
                    value = self.hardware.read(sensor)
                    self.db.save_test_sensor_value(
                        self.test['name'],
                        sensor,
                        value,
                        t_elapsed,
                        start_time)

                for point in self.test['points']:
                    if t.elapsed() < point['x']:
                        self.hardware.write(port, point['y'])
                        last_port_value = point['y']
                        self.db.save_test_sensor_value(
                            self.test['name'],
                            port,
                            point['y'],
                            t_elapsed,
                            start_time)
                        break
        except Exception as e:
            print(e)
            self.db.set_setting('test_error', str(e))

        self.db.save_test_sensor_value(
            self.test['name'],
            port,
            last_port_value,
            t.elapsed(),
            start_time)

        for o in self.test['afterOutputs']:
            self.hardware.write(o['alias'], o['value'])

        self.db.set_setting('current_test', None)
