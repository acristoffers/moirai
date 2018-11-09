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

import numpy as np
import scipy.signal

import json


class ModelSimulation(object):
    def __init__(self, data):
        self.data = data
        self.model = None
        self.x0 = None
        self.U = None
        self.T = None

    def run(self):
        try:
            self.model = [np.array(x) for x in eval(self.data['model'])]
        except:
            return json.dumps({'error': 'Invalid Model'})

        try:
            self.x0 = np.array(eval(self.data['x0']))
        except:
            return json.dumps({'error': 'Invalid x0'})

        try:
            self.U = eval(self.data['u'])
        except:
            return json.dumps({'error': 'Invalid U'})

        try:
            self.T = eval(self.data['duration'])
        except:
            return json.dumps({'error': 'Invalid Duration'})

        try:
            tf = len(self.model) < 4

            if len(self.model) % 2 == 1:
                dt = float(self.model[-1])
            else:
                if len(self.model) == 2:
                    self.model = scipy.signal.tf2ss(*self.model)
                vals = scipy.linalg.eigvals(self.model[0])
                dt = max(0.1, float('%.1f' % (max(abs(np.real(vals))) / 5)))
                if type(self.U) == list:
                    dt = self.T / len(self.U)
                self.model = scipy.signal.cont2discrete(self.model, dt)

            if type(self.U) == list:
                self.T = list(range(len(self.U)))
            else:
                self.T = list(range(int(self.T // dt)))
                self.U = [self.U for _ in self.T]

            A, B, C, D, _ = self.model
            x = self.x0 if not tf else np.zeros((A.shape[0], 1))
            outputs = {'u': self.U, 't': self.T}

            if C.shape[0] == 1:
                outputs['y'] = []
            else:
                for i in range(C.shape[0]):
                    outputs['y%d' % (i + 1)] = []

            if not tf:
                for i in range(len(x.flatten())):
                    outputs['x%d' % (i + 1)] = []

            for k in self.T:
                x = A @ x + B * self.U[k]
                y = C @ x + D * self.U[k]

                if not tf:
                    for i in range(len(x.flatten())):
                        k = i + 1
                        outputs['x%d' % k].append(np.asscalar(x.flatten()[i]))

                if C.shape[0] > 1:
                    for i in range(C.shape[0]):
                        k = i + 1
                        outputs['y%d' % k].append(np.asscalar(y.flatten()[i]))
                else:
                    outputs['y'].append(np.asscalar(y))

            outputs['t'] = [dt * k for k in outputs['t']]
            return json.dumps(outputs)
        except Exception as e:
            return json.dumps({'error': f'Error in simulation ({str(e)})'})
