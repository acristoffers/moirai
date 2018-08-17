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
import os

from moirai.database import DatabaseV1

# Port types:
# export enum Types {
#     Digital = 1,
#     Analog = 2,
#     Input = 4,
#     Output = 8,
#     PWM = 16
# }


class ConfiguredHardware(object):
    def __init__(self):
        self.db = DatabaseV1()
        config = self.db.get_setting('hardware_configuration')

        if config is None:
            raise Exception('No hardware configured')

        ahio.clear_path()
        try:
            paths = os.environ['AHIO_PATH'].split(os.pathsep)
            for path in paths:
                if os.path.exists(path):
                    ahio.add_path(os.path.expanduser(path))
        except Exception:
            pass

        self.driver = ahio.new_driver(config['name'])
        if config['has_setup']:
            args = {a['name']: a['value'] for a in config['setup_arguments']}
            self.driver.setup(**args)

        for port in config['ports']:
            pin = port['name']
            if hasattr(self.driver, 'Pins'):
                pin = self.driver.Pins(pin)
            self.driver.map_pin(port['id'], pin)

        self.inputs = [p for p in config['ports'] if p['type'] & 4]
        ps = [p['id'] for p in self.inputs]
        self.inputs = {
            p['alias']: lambda id=p['id']: self.driver.read(id)
            for p in self.inputs
        }
        cs = [c for c in config['calibrations'] if c['port'] in ps]
        cs = {
            c['alias']:
            lambda p=c['port'], f=c['formula']: self._read_calibrated(p, f)
            for c in cs
        }
        self.inputs = {**self.inputs, **cs}

        self.outputs = [p for p in config['ports'] if p['type'] & (8 | 16)]
        ps = {p['id']: p['type'] for p in self.outputs}
        self.outputs = {p['alias']: lambda x, id=p['id'], t=p['type']: self.driver.write(id, x, (t & 16) != 0)
                        for p in self.outputs}
        cs = [c for c in config['calibrations'] if c['port'] in ps.keys()]
        cs = {c['alias']: lambda x, p=c['port'], f=c['formula'], t=ps[c['port']]: self._write_calibrated(p, f, x, (t & 16) != 0)
              for c in cs}
        self.outputs = {**self.outputs, **cs}

    def _read_calibrated(self, port, formula):
        local = {'x': self.driver.read(port)}
        code = compile('y=%s' % formula, '_string_', 'exec')
        exec(code, local, local)
        return local['y']

    def _write_calibrated(self, port, formula, value, pwm):
        local = {'x': value}
        exec('y=%s' % formula, local, local)
        self.driver.write(port, local['y'], pwm)

    def read(self, port):
        f = self.inputs.get(port, None)
        if f is None:
            raise Exception(f'Port {port} not configured')
        return f()

    def write(self, port, value):
        f = self.outputs.get(port, None)
        if f is None:
            raise Exception(f'Port {port} not configured')
        f(value)
