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

import time


class Finished(Exception):
    pass


class Timer():
    def __init__(self, seconds, interval):
        self.seconds = seconds
        self.interval = interval
        self.start = time.time()
        self.t = time.time()

    def sleep(self):
        current_time = time.time()
        if current_time - self.start > self.seconds:
            raise Finished('Maximum time reached. Finished.')
        nextTime = current_time + self.interval
        nextTime -= (nextTime % self.interval)
        self.t = time.time()
        dt = nextTime - self.t
        if dt < 0:
            dt = 0
            print('Negative Δt in timer. Interval too short?')
        time.sleep(dt)

    def elapsed(self):
        return time.time() - self.start
