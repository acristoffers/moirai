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

import json
import time
import uuid

import mysql.connector


class DatabaseV1(object):
    """
    Database class. Connects to MongoDB and abstracts all communication with it.
    """

    def __init__(self,
                 host='127.0.0.1',
                 port=3306,
                 username=None,
                 password=None):
        self.params = {
            'host': host,
            'port': port,
            'user': username,
            'password': password,
            'autocommit': True
        }
        self.__init_db()
        self.token_lifespan = 24 * 3600

    def close(self):
        pass

    def set_setting(self, key, value):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = '''INSERT INTO moirai.settings (`key`, `value`)
                   VALUES (%s, %s) ON DUPLICATE KEY
                   UPDATE `key` = values(`key`), `value` = values(`value`)'''
        cur.execute(query, (key, json.dumps(value)))
        cur.close()
        cnx.close()

    def get_setting(self, key):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = 'SELECT `key`, `value` FROM moirai.settings WHERE `key` = %s'
        cur.execute(query, (key, ))
        r = [json.loads(value) for (key, value) in cur]
        return r[0] if len(r) > 0 else None
        cur.close()
        cnx.close()

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
        t = {'token': uuid.uuid4().hex, 'time': time.time()}
        ts = self.get_setting('tokens') or []
        ts += [t]
        ts = [t for t in ts if time.time() - t['time'] < self.token_lifespan]
        self.set_setting('tokens', ts)
        return t['token']

    def save_test_sensor_value(self, test, sensor, value, time, start_time):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = '''INSERT INTO moirai.sensor_values
                   (sensor, value, time, start_time, test)
                   VALUES (%s, %s, %s, %s, %s)'''
        cur.execute(query, (sensor, value, time, start_time, test))
        cur.close()
        cnx.close()

    def list_test_data(self):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = 'SELECT DISTINCT test, start_time FROM moirai.sensor_values'
        cur.execute(query)
        r = [{'name': test, 'date': start_time} for (test, start_time) in cur]
        cur.close()
        cnx.close()
        return r

    def get_test_data(self, test, start_time, skip=0):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = '''SELECT `sensor`, `time`, `value` FROM moirai.sensor_values
                   WHERE test = %s AND start_time = %s ORDER BY time LIMIT 1000000 OFFSET %s'''
        cur.execute(query, (test, start_time, skip))
        r = [{
            'sensor': sensor,
            'time': time,
            'value': value
        } for (sensor, time, value) in cur]
        cur.close()
        cnx.close()
        return r

    def get_filtered_test_data(self, test, start_time, sensors):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = '''SELECT `time`, `value` FROM moirai.sensor_values
                   WHERE test = %s AND start_time = %s AND sensor = %s'''
        result = []
        for sensor in sensors:
            s = {'sensor': sensor, 'time': [], 'values': []}
            cur.execute(query, (test, start_time, sensor))
            s['time'], s['values'] = zip(*cur)
            result.append(s)
        cur.close()
        cnx.close()
        return result

    def remove_test(self, test):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = '''DELETE FROM moirai.sensor_values 
                   WHERE `test` = %s AND `start_time` = %s'''
        if isinstance(test, list):
            d = [(t['test'], t['start_time']) for t in test]
            cur.executemany(query, d)
        else:
            cur.execute(query, (test['test'], test['start_time']))
        cur.close()
        cnx.close()

    def dump_database(self):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        cur.execute('SELECT `key`, `value` FROM moirai.settings')
        settings = [{
            'key': key,
            'value': json.loads(value)
        } for (key, value) in cur]
        cur.execute('''SELECT `sensor`, `value`, `time`, `start_time`, `test` 
                       FROM moirai.sensor_values''')
        sensor_values = [{
            'sensor': sensor,
            'value': value,
            'time': time,
            'start_time': start_time,
            'test': test
        } for (sensor, value, time, start_time, test) in cur]
        cur.close()
        cnx.close()
        return settings, sensor_values

    def restore_database(self, settings, test_sensor_values):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        cur.execute('DROP DATABASE IF EXISTS `moirai`')
        self.__init_db()
        query = '''INSERT INTO moirai.settings (`key`, `value`)
                   VALUES (%s, %s) ON DUPLICATE KEY
                   UPDATE `key` = values(`key`), `value` = values(`value`)'''
        data = [(s['key'], json.dumps(s['value'])) for s in settings]
        cur.executemany(query, data)

        query = '''INSERT INTO moirai.sensor_values 
                    (`sensor`, `value`, `time`, `start_time`, `test`)
                   VALUES (%s, %s, %s, %s, %s)'''
        data = [(s['sensor'], s['value'], s['time'], s['start_time'],
                 s['test']) for s in test_sensor_values]
        for d in (data[i:i + 100] for i in range(0, len(data), 100)):
            cur.executemany(query, d)
        cur.close()
        cnx.close()

    def __cnx(self):
        return mysql.connector.connect(**self.params)

    def __init_db(self):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        cur.execute('SET @@local.net_read_timeout=3600;')
        cur.execute(
            'CREATE SCHEMA IF NOT EXISTS `moirai` DEFAULT CHARACTER SET utf8')
        cur.execute('USE moirai')
        cur.execute('''CREATE TABLE IF NOT EXISTS `moirai`.`settings`
                       (`id` INT NOT NULL AUTO_INCREMENT,
                       `value` LONGTEXT NULL,
                       `key` VARCHAR(100) NOT NULL,
                       PRIMARY KEY (`id`), UNIQUE INDEX `key_UNIQUE` (`id` ASC),
                       UNIQUE INDEX `key_idx` (`key` ASC))
                       ENGINE = InnoDB DEFAULT CHARACTER SET = utf8''')
        cur.execute('''CREATE TABLE IF NOT EXISTS `moirai`.`sensor_values` 
                       ( `id` INT NOT NULL AUTO_INCREMENT,
                       `sensor` VARCHAR(100) NOT NULL, `value` DOUBLE NOT NULL,
                       `time` FLOAT NOT NULL, `start_time` DATETIME NOT NULL,
                       `test` VARCHAR(100) NOT NULL, PRIMARY KEY (`id`),
                       UNIQUE INDEX `id_UNIQUE` (`id` ASC), INDEX `sensor_idx`
                       USING BTREE (`sensor` ASC),
                       INDEX `time_idx` (`time` ASC),
                       INDEX `start_time_idx` (`start_time` ASC),
                       INDEX `test_idx` (`test` ASC))
                       ENGINE = InnoDB DEFAULT CHARACTER SET = utf8''')
        cur.close()
        cnx.close()
