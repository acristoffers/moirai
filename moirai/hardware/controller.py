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

import numpy as np
import math

from moirai.database import DatabaseV1
from moirai.hardware.configured_hardware import ConfiguredHardware
from moirai.hardware.timer import Timer


class Controller(object):
    def __init__(self, controller_id):
        self.db = DatabaseV1()
        cs = self.db.get_setting('controllers')
        self.cs = next((c for c in cs if c['id'] == controller_id), None)
        if self.cs is None:
            raise Exception('Controller not found')
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
        run_time = int(self.cs['runTime'])
        interval = float(self.cs['tau'])
        t = Timer(run_time, interval)
        start_time = datetime.datetime.utcnow()

        self.db.set_setting('current_test', self.cs['name'])

        after = None

        try:
            before = compile(self.cs['before'], '_string_', 'exec')
            controller = compile(self.cs['controller'], '_string_', 'exec')
            after = compile(self.cs['after'], '_string_', 'exec')

            inputs = {s: self.hardware.read(s) for s in self.cs['inputs']}
            plocals = {
                'inputs': inputs,
                'outputs': dict(),
                's': dict()
            }
            pglobals = {
                'np': np,
                'math': math
            }
            exec(before, pglobals, plocals)

            state = plocals['s']

            for k, v in plocals['outputs'].items():
                self.hardware.write(k, v)

            while self.db.get_setting('current_test') is not None:
                t.sleep()
                time = t.elapsed()

                for lock in self.locks:
                    lock()

                inputs = {s: self.hardware.read(s) for s in self.cs['inputs']}
                plocals = {
                    'inputs': inputs,
                    'outputs': dict(),
                    's': state,
                    'log': dict()
                }
                pglobals = {
                    'np': np,
                    'math': math
                }
                exec(controller, pglobals, plocals)

                plocals['log'] = {
                    **plocals['log'],
                    **plocals['inputs'],
                    **plocals['outputs']
                }

                for k, v in plocals['outputs'].items():
                    self.hardware.write(k, v)

                for k, v in plocals['log'].items():
                    cid = self.cs['name']
                    self.db.save_test_sensor_value(cid, k, v, time, start_time)

                state = plocals['s']
        except Exception as e:
            print(e)
            self.db.set_setting('test_error', str(e))

        if after is not None:
            inputs = {s: self.hardware.read(s) for s in self.cs['inputs']}
            plocals = {
                'inputs': inputs,
                'outputs': dict()
            }
            pglobals = {
                'np': np,
                'math': math
            }
            exec(after, pglobals, plocals)

            for actuator, value in plocals['outputs'].items():
                self.hardware.write(actuator, value)

        self.db.set_setting('current_test', None)
