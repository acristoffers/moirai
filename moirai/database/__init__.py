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
import uuid

from pymongo import MongoClient


class DatabaseV1(object):
    def __init__(self):
        self.client = MongoClient()
        self.db = self.client.moirai
        self.token_lifespan = 5 * 60

    def settings_collection(self):
        return self.db.settings

    def set_setting(self, key, value):
        db = self.settings_collection()
        db.replace_one({"key": key}, {"key": key, "value": value}, upsert=True)

    def get_setting(self, key):
        db = self.settings_collection()
        document = db.find_one({"key": key})
        if document:
            return document['value']
        else:
            return None

    def verify_token(self, token):
        ts = self.get_setting('tokens')
        ts = [t for t in ts if t['token'] == token and
              time.time() - t['time'] < self.token_lifespan]
        return len(ts) > 0

    def generate_token(self):
        t = {
            'token': uuid.uuid4().hex,
            'time': time.time()
        }
        ts = self.get_setting('tokens') or []
        ts += [t]
        ts = [t for t in ts if time.time() - t['time'] < self.token_lifespan]
        self.set_setting('tokens', ts)
        return t['token']
