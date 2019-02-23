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

import datetime
import math
import sys
import time
import traceback

from moirai.database import DatabaseV1
from moirai.hardware.configured_hardware import ConfiguredHardware
from moirai.hardware.timer import Timer


class Free(object):
    __instance = None

    @classmethod
    def instance(cls):
        if not Free.__instance:
            Free.__instance = Free()
        return Free.__instance

    def __init__(self):
        self.last_run = time.time()
        self.running = False
        self.timer = Timer(math.inf, 1)
        self.hardware = None
        self.db = DatabaseV1()
        self.start_time = datetime.datetime.utcnow()
        self.locks = []
        self.inputs = []
        self.outputs = []

    def is_valid(self):
        return (time.time() - self.last_run) < max(2 * self.timer.interval, 1)

    def run(self, data=None):
        try:
            if data:
                self.last_run = time.time()
                self.running = True
                self.timer.interval = float(data['dt'])
                self.inputs = data['inputs']
                self.outputs = [
                    o for o in data['outputs'] if len(o['alias']) != 0
                ]
                config = self.db.get_setting('hardware_configuration')
                self.locks = [self.interlock(l) for l in config['interlocks']]

            if not self.is_valid():
                self.running = False

            if self.running:
                if not self.hardware:
                    self.db.set_setting('test_error', '')
                    self.timer = Timer(math.inf, float(data['dt']))
                    self.start_time = datetime.datetime.utcnow()
                    self.hardware = ConfiguredHardware()
                    self.last_run = time.time()

                    for output in self.outputs:
                        self.db.save_test_sensor_value('Free', output['alias'],
                                                       0, 0, self.start_time)
                    for input in self.inputs:
                        self.db.save_test_sensor_value('Free', input, 0, 0,
                                                       self.start_time)

                self.timer.sleep()

                for output in self.outputs:
                    self.hardware.write(output['alias'], output['value'])
                    self.db.save_test_sensor_value(
                        'Free', output['alias'], output['value'],
                        self.timer.elapsed(), self.start_time)

                for input in self.inputs:
                    value = self.hardware.read(input)
                    self.db.save_test_sensor_value('Free', input, value,
                                                   self.timer.elapsed(),
                                                   self.start_time)

                for lock in self.locks:
                    lock()
            elif self.hardware:
                self.shutdown()
        except Exception as e:
            print(e)
            self.running = False
            self.shutdown()

    def shutdown(self):
        if self.hardware:
            self.off_values = {
                p['alias']: float(p['defaultValue'])
                for p in self.hardware.ports if p['type'] & (8 | 16)
            }
            for k, v in self.off_values.items():
                self.hardware.write(k, v)
            self.hardware = None

    def interlock(self, lock):
        try:
            code = compile('y=%s' % lock['expression'], '_string_', 'exec')
        except SyntaxError as err:
            error = err.__class__.__name__
            detail = err.args[0]
            line = err.lineno
            error_string = '%s on %s:%s: %s' % (error, 'pid', line, detail)
            print(error_string)
            self.db.set_setting('test_error', error_string)
            self.running = False
            return

        def f(code=code, lock=lock):
            try:
                value = self.hardware.read(lock['sensor'])
                scope = {'x': value}
                exec(code, None, scope)
            except Exception as err:
                error = err.__class__.__name__
                detail = err.args[0]
                cl, exc, tb = sys.exc_info()
                tb = self.stringify_tb(traceback.extract_tb(tb))
                error_string = '%s: %s\n%s' % (error, detail, tb)
                print(error_string)
                self.db.set_setting('test_error', error_string)
                raise Exception('Interlock')
            if scope['y']:
                self.hardware.write(lock['actuator'], lock['actuatorValue'])
                self.db.set_setting('test_error', 'Interlock')
                raise Exception('Interlock')

        return f

    def stringify_tb(self, tb):
        msg = 'Traceback:\n\t'
        msg += '\n\t'.join(
            ['%s:%s in %s' % (t.filename, t.lineno, t.name) for t in tb])
        return msg
