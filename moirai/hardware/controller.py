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
import threading
import time

import sys
import os

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
        self.running = True
        self.lock = threading.Lock()
        self.after = None

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

    def lock_forever(self):
        interval = float(self.cs['tau'])
        while self.running:
            time.sleep(interval)
            self.lock.acquire()
            try:
                for lock in self.locks:
                    lock()
            except:
                self.running = False
                if self.after is not None:
                    ins = self.cs['inputs']
                    inputs = {s: self.hardware.read(s) for s in ins}
                    plocals = {
                        'inputs': inputs,
                        'outputs': dict(),
                        'np': np,
                        'math': math
                    }
                    exec(self.after, plocals, plocals)

                    for actuator, value in plocals['outputs'].items():
                        self.hardware.write(actuator, value)
            self.lock.release()

    def run(self):
        run_time = int(self.cs['runTime'])
        interval = float(self.cs['tau'])
        t = Timer(run_time, interval)
        start_time = datetime.datetime.utcnow()

        self.db.set_setting('current_test', self.cs['name'])

        after = None
        self.running = True

        try:
            before = compile(self.cs['before'], '_string_', 'exec')
            controller = compile(self.cs['controller'], '_string_', 'exec')
            after = compile(self.cs['after'], '_string_', 'exec')
            self.after = after

            thread = threading.Thread(target=self.lock_forever)
            thread.start()
            thread.isDaemon = True

            inputs = {s: self.hardware.read(s) for s in self.cs['inputs']}
            plocals = {
                'inputs': inputs,
                'outputs': dict(),
                's': dict(),
                'np': np,
                'math': math
            }

            exec(before, plocals, plocals)

            state = plocals['s']

            for k, v in plocals['outputs'].items():
                self.hardware.write(k, v)

            while self.db.get_setting('current_test') is not None and self.running:
                t.sleep()
                time = t.elapsed()

                self.lock.acquire()
                inputs = {s: self.hardware.read(s) for s in self.cs['inputs']}
                self.lock.release()

                plocals = {
                    'inputs': inputs,
                    'outputs': dict(),
                    's': state,
                    'log': dict(),
                    't': time,
                    'np': np,
                    'math': math
                }

                exec(controller, plocals, plocals)

                plocals['log'] = {
                    **plocals['log'],
                    **plocals['inputs'],
                    **plocals['outputs']
                }

                self.lock.acquire()
                for k, v in plocals['outputs'].items():
                    self.hardware.write(k, v)

                for k, v in plocals['log'].items():
                    cid = self.cs['name']
                    self.db.save_test_sensor_value(cid, k, v, time, start_time)
                self.lock.release()

                state = plocals['s']
        except Exception as e:
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            self.db.set_setting('test_error', str(e))

        if after is not None:
            inputs = {s: self.hardware.read(s) for s in self.cs['inputs']}
            plocals = {
                'inputs': inputs,
                'outputs': dict(),
                'np': np,
                'math': math
            }

            exec(after, plocals, plocals)

            for actuator, value in plocals['outputs'].items():
                self.hardware.write(actuator, value)

        self.db.set_setting('current_test', None)
        self.running = False
