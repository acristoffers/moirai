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

from moirai.decorators import decorate_all_methods, dont_raise, log_msg
from enum import Enum
import ahio
import json


def can_dump(obj):
    try:
        json.dumps(obj)
    except:
        return False
    return True


def port_dump(port):
    """If the port is a Enum, us its value. If it's a value that can be dumped
    to JSON, use it, if not, raise an exception.
    """
    id_ = None
    if isinstance(port['id'], Enum):
        id_ = port['id'].value
    elif can_dump(port['id']):
        id_ = port['id']
    else:
        raise TypeError('Port ID must be an Enum or JSON.dumps\'able object')
    port['id'] = id_
    return port


def port_load(port, driver):
    """If the ID in port should be converted to Enum, do it. Else, keep it as
    it is.
    """
    ps = driver.available_pins()
    if len(ps) > 0:
        p = ps[0]
        if isinstance(p['id'], Enum):
            port['id'] = p['id'].__class__(port['id'])
    return port


def bool_to_logic(boolean):
    if boolean:
        return ahio.LogicValue.High
    else:
        return ahio.LogicValue.Low


def bool_to_type(boolean):
    if boolean:
        return ahio.PortType.Digital
    else:
        return ahio.PortType.Analog


def bool_to_direction(boolean):
    if boolean:
        return ahio.Direction.Input
    else:
        return ahio.Direction.Output


@decorate_all_methods(dont_raise)
class HardwareLayer(object):

    def __init__(self, process_handler):
        self.handler = process_handler
        self.driver = None

    def instantiate_driver(self, name):
        if name in ahio.list_available_drivers():
            self.driver = ahio.new_driver(name)
        else:
            log_msg('No such ahio driver: %s' % name)

    def setup(self, args={}):
        if self.driver:
            try:
                self.driver.setup(**args)
            except:
                return False
        return True

    def list_ports(self):
        if self.driver != None:
            return [port_dump(port) for port in self.driver.available_pins()]
        else:
            return []

    def config_port(self, port):
        port = port_load(port, self.driver)
        _id = port['map']
        self.driver.map_pin(_id, port['id'])
        self.driver.set_pin_type(_id, bool_to_type(port['digital']))
        self.driver.set_pin_direction(_id, bool_to_direction(port['input']))
        if not port['input']:
            if port['pwm']:
                self.driver.write(_id, port['value'], port['pwm'])
            else:
                self.driver.write(_id, bool_to_logic(
                    port['value']), port['pwm'])

    def loop(self):
        pass
