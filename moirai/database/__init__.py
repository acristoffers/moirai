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

"""
Database class. Connects to MongoDB and abstracts all communication with it.
"""

import time
import uuid

from pymongo import MongoClient


class DatabaseV1(object):
    """
    Database class. Connects to MongoDB and abstracts all communication with it.
    """

    def __init__(self):
        self.client = MongoClient()
        self.db = self.client.moirai
        self.token_lifespan = 24 * 3600
        self.__create_indexes()

    def close(self):
        self.client.close()

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
        now = time.time()
        span = self.token_lifespan
        ts = self.get_setting('tokens')
        vs = [t for t in ts if t['token'] == token and now - t['time'] < span]
        if len(vs) > 0:
            ts = [t for t in ts if t['token'] != token]
            ts.append({'token': token, 'time': now})
            self.set_setting('tokens', ts)
            return True
        return False

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

    def save_test_sensor_value(self, test, sensor, value, time, start_time):
        db = self.db.test_sensor_values
        data = {
            'test': test,
            'sensor': sensor,
            'value': value,
            'time': time,
            'start_time': start_time
        }
        db.insert_one(data)

    def list_test_data(self):
        db = self.db.test_sensor_values
        cursor = db.aggregate([
            {
                '$match': {
                    'time': {
                        '$lt': 1
                    }
                }
            },
            {
                '$group': {
                    '_id': {
                        'name': '$test',
                        'date': '$start_time'
                    }
                }
            },
            {
                '$replaceRoot': {
                    'newRoot': "$_id"
                }
            }
        ])

        return list(cursor)

    def get_test_data(self, test, start_time, skip=0):
        db = self.db.test_sensor_values

        cursor = db.aggregate([
            {
                '$match': {
                    'test': test,
                    'start_time': start_time
                }
            },
            {
                '$sort': {
                    'time': 1
                }
            },
            {
                '$skip': skip
            },
            {
                '$project': {
                    'sensor': 1,
                    'time': 1,
                    'value': 1,
                    '_id': 0
                }
            }
        ])

        return list(cursor)

    def remove_test(self, test, start_time):
        self.db.test_sensor_values.delete_many({
            'test': test,
            'start_time': start_time
        })

    def __create_indexes(self):
        self.db.test_sensor_values.create_index('time', name='time')
        self.db.test_sensor_values.create_index('st', name='start_time')
        self.db.test_sensor_values.create_index('test', name='test')
