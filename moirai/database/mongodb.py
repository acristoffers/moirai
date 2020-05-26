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
    Database class. Connects to MongoDB and abstracts all communication.
    """

    def __init__(self):
        self.client = MongoClient()
        self.db = self.client.moirai
        self.token_lifespan = 24 * 3600
        self.__migrate()
        self.__create_indexes()
        self.set_setting('version', '1.0')

    def close(self):
        self.client.close()

    def set_setting(self, key, value):
        db = self.db.settings
        db.replace_one({"key": key}, {"key": key, "value": value}, upsert=True)

    def get_setting(self, key):
        db = self.db.settings
        document = db.find_one({"key": key})
        if document:
            return document['value']
        else:
            return None

    def verify_token(self, token):
        now = int(time.time())
        span = self.token_lifespan
        ts = self.get_setting('tokens')
        vs = [t for t in ts if t['token'] == token and now - t['time'] < span]
        if vs:
            ts = [t for t in ts if t['token'] != token]
            ts.append({'token': token, 'time': now})
            ts = [t for t in ts if now - t['time'] < span]
            self.set_setting('tokens', ts)
            return True
        return False

    def generate_token(self):
        t = {'token': uuid.uuid4().hex, 'time': time.time()}
        ts = self.get_setting('tokens') or []
        ts += [t]
        ts = [t for t in ts if time.time() - t['time'] < self.token_lifespan]
        self.set_setting('tokens', ts)
        return t['token']

    def save_test(self, name, date):
        graph = {'name': name, 'date': date}
        self.db.graphs.insert_one(graph)
        return graph['_id']

    def save_test_sensor_value(self, graph_id, sensor, value, time):
        value = value if isinstance(value, int) else float(value)
        data = {
            'sensor': sensor,
            'value': value,
            'time': time,
            'graph': graph_id
        }
        self.db.graphs_data.insert_one(data)

    def list_test_data(self):
        cursor = self.db.graphs.find()
        tests = [{'name': t['name'], 'date': t['date']} for t in cursor]
        return tests

    def get_test_data(self, test, start_time, skip=0):
        oid = self.db.graphs.find_one({
            'name': test,
            'date': start_time
        })['_id']
        cursor = self.db.graphs_data.aggregate([{
            '$match': {
                'graph': oid
            }
        }, {
            '$sort': {
                'time': 1
            }
        }, {
            '$skip': skip
        }, {
            '$project': {
                'sensor': 1,
                'time': 1,
                'value': 1,
                '_id': 0
            }
        }])
        return list(cursor)

    def get_filtered_test_data(self, test, start_time, sensors):
        oid = self.db.graphs.find_one({
            'name': test,
            'date': start_time
        })['_id']
        match = {'$match': {'graph': oid, 'sensor': {'$in': sensors}}}
        sort = {'$sort': {'time': 1}}
        group = {
            '$group': {
                '_id': '$sensor',
                'values': {
                    '$push': '$value'
                },
                'time': {
                    '$push': '$time'
                }
            }
        }
        project = {
            '$project': {
                'time': 1,
                'sensor': '$_id',
                'values': 1,
                '_id': 0
            }
        }
        cursor = self.db.graphs_data.aggregate([match, sort, group, project])
        return list(cursor)

    def remove_test(self, test):
        tests = test if isinstance(test, list) else [test]
        for test in tests:
            oid = self.db.graphs.find_one(test)['_id']
            self.db.graphs.delete_one({'_id': oid})
            self.db.graphs_data.delete_many({'graph': oid})

    def dump_database(self):
        graphs = list(self.db.graphs.find())
        for graph in graphs:
            graph['data'] = []
            for point in self.db.graphs_data.find({'graph': graph['_id']}):
                del point['_id']
                del point['graph']
                graph['data'].append(point)
            del graph['_id']
        settings = self.db.settings.find({}, {'_id': 0})
        return list(settings), list(graphs)

    def restore_database_v2(self, settings, graphs):
        self.db.settings.drop()
        self.db.graphs.drop()
        self.db.graphs_data.drop()
        self.db.settings.insert_many(settings)
        for graph in graphs:
            g = {'name': graph['name'], 'date': graph['date']}
            self.db.graphs.insert_one(g)
            for point in graph['data']:
                point['graph'] = g['_id']
            self.db.graphs_data.insert_many(graph['data'])
        self.set_setting('version', '1.0')

    def restore_database_v1(self, settings, test_sensor_values):
        self.db.settings.drop()
        self.db.graphs.drop()
        self.db.graphs_data.drop()
        self.db.settings.insert_many(settings)
        self.db.test_sensor_values.insert_many(test_sensor_values)
        self.__migrate()

    def __create_indexes(self):
        self.db.graphs_data.create_index('time', name='time')
        self.db.graphs_data.create_index('graph', name='graph')

    def __migrate(self):
        if self.get_setting('version') is None:
            match = {'$match': {'time': {'$lt': 1}}}
            group = {
                '$group': {
                    '_id': {
                        'name': '$test',
                        'date': '$start_time'
                    }
                }
            }
            project = {
                '$project': {
                    '_id': 0,
                    'name': '$_id.name',
                    'date': '$_id.date'
                }
            }
            query = [match, group, project]
            cursor = self.db.test_sensor_values.aggregate(query)
            tests = list(cursor)
            if tests:
                self.db.graphs.insert_many(tests)
                for test in tests:
                    oid = test['_id']
                    match = {
                        '$match': {
                            'test': test['name'],
                            'start_time': test['date']
                        }
                    }
                    project = {
                        '$project': {
                            '_id': 0,
                            'time': 1,
                            'sensor': 1,
                            'value': 1,
                            'graph': oid
                        }
                    }
                    query = [match, project]
                    cursor = self.db.test_sensor_values.aggregate(query)
                    self.db.graphs_data.insert_many(cursor)
                self.db.test_sensor_values.drop()
                self.set_setting('version', '1.0')
