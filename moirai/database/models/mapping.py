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

from orator import Model


def _objectify(m):
    return {
        'id': m.driver_id,
        'alias': m.alias,
        'digital': m.digital,
        'input': m.input,
        'pwm': m.pwm,
        'value': m.initial_value,
        'map': m.ahio_id
    }


class Mappings(Model):

    @staticmethod
    def set(mappings):
        for m in Mappings.all():
            m.delete()
        for d in mappings:
            m = Mappings()
            m.driver_id = d['id']
            m.alias = d['alias']
            m.digital = d['digital']
            m.input = d['input']
            m.pwm = d['pwm']
            m.initial_value = d['value']
            m.ahio_id = d['map']
            m.save()

    @staticmethod
    def get():
        ms = Mappings.all()
        return [_objectify(m) for m in ms]
