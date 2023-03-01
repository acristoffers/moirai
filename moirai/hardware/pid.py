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


class PID(object):
    __instance = None

    @classmethod
    def instance(cls):
        if not PID.__instance:
            PID.__instance = PID()
        return PID.__instance

    def __init__(self):
        self.last_run = time.time()
        self.running = False
        self.timer = Timer(math.inf, 1)
        self.Kp = 0
        self.Ki = 0
        self.Kd = 0
        self.y = ""
        self.u = ""
        self.le = 0
        self.se = 0
        self.li = 0
        self.ls = 0
        self.fixedOutputs = []
        self.hardware = None
        self.db = DatabaseV1()
        self.start_time = datetime.datetime.utcnow()
        self.locks = []
        self.graph_id = None

    def is_valid(self):
        return (time.time() - self.last_run) < max(2 * self.timer.interval, 1)

    def run(self, data=None):
        try:
            if data:
                self.last_run = time.time()
                self.running = True
                self.timer.interval = float(data["dt"])
                self.Kp = float(data["Kp"])
                self.Ki = float(data["Ki"])
                self.Kd = float(data["Kd"])
                self.r = float(data["r"])
                self.li = float(data["umin"])
                self.ls = float(data["umax"])
                self.y = data["y"]
                self.u = data["u"]
                self.fixedOutputs = [
                    o for o in data["fixedOutputs"] if len(o["alias"]) != 0
                ]
                config = self.db.get_setting("hardware_configuration")
                self.locks = list(map(self.interlock, config["interlocks"]))

            if not self.is_valid():
                self.running = False

            if self.running:
                if not self.hardware:
                    self.db.set_setting("test_error", "")
                    self.timer = Timer(math.inf, float(data["dt"]))
                    self.start_time = datetime.datetime.utcnow()
                    self.hardware = ConfiguredHardware()
                    self.last_run = time.time()
                    self.graph_id = self.db.save_test("PID", self.start_time)

                    for output in self.fixedOutputs:
                        self.hardware.write(output["alias"], output["value"])

                    save = self.db.save_test_sensor_value
                    save(self.graph_id, self.y, 0, 0)
                    save(self.graph_id, self.u, 0, 0)
                    save(self.graph_id, "R", self.r, 0)

                self.timer.sleep()

                y = self.hardware.read(self.y)
                e = self.r - y
                de = e - self.le
                self.se += e
                u = self.Kp * e + self.Kd * de + self.Ki * self.se
                u = sorted([self.li, self.ls, u])[1]
                self.hardware.write(self.u, u)
                self.le = e

                save = self.db.save_test_sensor_value
                save(self.graph_id, self.y, y, self.timer.elapsed())
                save(self.graph_id, self.u, u, self.timer.elapsed())
                save(self.graph_id, "R", self.r, self.timer.elapsed())

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
                p["alias"]: float(p["defaultValue"])
                for p in self.hardware.ports
                if p["type"] & (8 | 16)
            }
            for k, v in self.off_values.items():
                self.hardware.write(k, v)
            self.hardware = None

    def interlock(self, lock):
        try:
            code = compile("y=%s" % lock["expression"], "_string_", "exec")
        except SyntaxError as err:
            error = err.__class__.__name__
            detail = err.args[0]
            line = err.lineno
            error_string = "%s on %s:%s: %s" % (error, "pid", line, detail)
            print(error_string)
            self.db.set_setting("test_error", error_string)
            self.running = False
            return

        def f(code=code, lock=lock):
            try:
                value = self.hardware.read(lock["sensor"])
                scope = {"x": value}
                exec(code, None, scope)
            except Exception as err:
                error = err.__class__.__name__
                detail = err.args[0]
                cl, exc, tb = sys.exc_info()
                tb = self.stringify_tb(traceback.extract_tb(tb))
                error_string = "%s: %s\n%s" % (error, detail, tb)
                print(error_string)
                self.db.set_setting("test_error", error_string)
                raise Exception("Interlock")
            if scope["y"]:
                self.hardware.write(lock["actuator"], lock["actuatorValue"])
                self.db.set_setting("test_error", "Interlock")
                raise Exception("Interlock")

        return f

    def stringify_tb(self, tb):
        msg = "Traceback:\n\t"
        msg += "\n\t".join(["%s:%s in %s" % (t.filename, t.lineno, t.name) for t in tb])
        return msg
