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
Database class. Connects to MySQL and abstracts all communication with it.
"""

import json
import time
import uuid
from multiprocessing import Lock

import mysql.connector


class DatabaseV1(object):
    """
    Database class. Connects to MySQL and abstracts all communication with it.
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
        self.__migrate()
        self.token_lifespan = 24 * 3600
        self._mutex = Lock()

    def close(self):
        pass

    def set_setting(self, key, value):
        with self._mutex:
            cnx = self.__cnx()
            cur = cnx.cursor(True)
            query = '''INSERT INTO `moirai`.`settings` (`key`, `value`)
                    VALUES (%s, %s) ON DUPLICATE KEY
                    UPDATE `key` = values(`key`), `value` = values(`value`)'''
            cur.execute(query, (key, json.dumps(value)))
            cur.close()
            cnx.close()

    def get_setting(self, key):
        with self._mutex:
            cnx = self.__cnx()
            cur = cnx.cursor(True)
            query = 'SELECT `value` FROM `moirai`.`settings` WHERE `key` = %s'
            cur.execute(query, (key, ))
            r = [json.loads(value) for (value, ) in cur]
            cur.close()
            cnx.close()
            return r[0] if len(r) > 0 else None

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
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        q = 'INSERT INTO `moirai`.`graphs` (`name`, `date`) VALUES (%s, %s)'
        cur.execute(q, (name, date))
        cur.execute('SELECT LAST_INSERT_ID()')
        rowid = list(cur)[0][0]
        cur.close()
        cnx.close()
        return rowid

    def save_test_sensor_value(self, graph_id, sensor, value, time):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = '''INSERT INTO `moirai`.`graphs_data`
                        (`sensor`, `value`, `time`, `graph`)
                        VALUES (%s, %s, %s, %s)'''
        value = value if isinstance(value, int) else float(value)
        cur.execute(query, (sensor, value, time, graph_id))
        cur.close()
        cnx.close()

    def list_test_data(self):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = 'SELECT `name`, `date` FROM `moirai`.`graphs`'
        cur.execute(query)
        r = [{'name': name, 'date': date} for (name, date) in cur]
        cur.close()
        cnx.close()
        return r

    def get_test_data(self, name, date, skip=0):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = '''
            SELECT `sensor`, `time`, `value` FROM `moirai`.`graphs_data`
                LEFT JOIN `moirai`.`graphs`
                ON `graphs`.`id`=`graphs_data`.`graph`
                WHERE `graphs`.`name`=%s AND `graphs`.`date`=%s
                ORDER BY `graphs_data`.`time` LIMIT 1000000 OFFSET %s
            '''
        cur.execute(query, (name, date, skip))
        r = [{
            'sensor': sensor,
            'time': time,
            'value': value
        } for (sensor, time, value) in cur]
        cur.close()
        cnx.close()
        return r

    def get_filtered_test_data(self, name, date, sensors):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = '''
            SELECT `time`, `value` FROM `moirai`.`graphs_data`
                LEFT JOIN `moirai`.`graphs`
                ON `graphs`.`id`=`graphs_data`.`graph`
                WHERE `graphs`.`name`=%s AND `graphs`.`date`=%s
                AND `graphs_data`.`sensor`=%s
                ORDER BY `graphs_data`.`time`
            '''
        result = []
        for sensor in sensors:
            s = {'sensor': sensor, 'time': [], 'values': []}
            cur.execute(query, (name, date, sensor))
            s['time'], s['values'] = zip(*cur)
            result.append(s)
        cur.close()
        cnx.close()
        return result

    def remove_test(self, test):
        tests = test if isinstance(test, list) else [test]
        tests = [(t['name'], t['date']) for t in tests]
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        query = 'DELETE FROM `moirai`.`graphs` WHERE `name`=%s AND `date`=%s'
        cur.executemany(query, tests)
        cur.close()
        cnx.close()

    def dump_database(self):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        cur.execute('SELECT `key`, `value` FROM `moirai`.`settings`')
        settings = [{
            'key': key,
            'value': json.loads(value)
        } for (key, value) in cur]
        cur.execute('SELECT `id`, `name`, `date` FROM `moirai`.`graphs`')
        graphs = [{
            'id': oid,
            'name': name,
            'date': date
        } for oid, name, date in cur]
        query = '''SELECT `sensor`, `time`, `value` FROM `moirai`.`graphs_data`
                    WHERE `graph`=%s'''
        for graph in graphs:
            cur.execute(query, (graph['id'], ))
            graph['data'] = [{
                'sensor': sensor,
                'time': time,
                'value': value
            } for sensor, time, value in cur]
            del graph['id']
        cur.close()
        cnx.close()
        return settings, graphs

    def restore_database_v2(self, settings, graphs):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        cur.execute('DROP DATABASE IF EXISTS `moirai`')
        self.__init_db()
        query = '''
                INSERT INTO `moirai`.`settings` (`key`, `value`)
                    VALUES (%s, %s) ON DUPLICATE KEY
                    UPDATE `key` = values(`key`), `value` = values(`value`)
                '''
        data = [(s['key'], json.dumps(s['value'])) for s in settings]
        cur.executemany(query, data)
        for graph in graphs:
            query = '''INSERT INTO `moirai`.`graphs` (`name`, `date`)
                            VALUES (%s, %s)'''
            cur.execute(query, (graph['name'], graph['date']))
            cur.execute('SELECT LAST_INSERT_ID()')
            rowid = list(cur)[0][0]
            data = [(d['sensor'], d['time'], d['value'], rowid)
                    for d in graph['data']]
            query = '''INSERT INTO `moirai`.`graphs_data`
                            (`sensor`, `time`, `value`, `graph`)
                            VALUES (%s, %s, %s, %s)'''
            cur.executemany(query, data)
        cur.close()
        cnx.close()

    def restore_database_v1(self, settings, test_sensor_values):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        cur.execute('DROP DATABASE IF EXISTS `moirai`')
        self.__init_db()
        cur.execute('USE moirai')
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
        cur.execute('DELETE FROM `moirai`.`settings` WHERE `key`="version"')
        cur.close()
        cnx.close()
        self.__migrate()

    def __cnx(self):
        return mysql.connector.connect(**self.params)

    def __init_db(self):
        cnx = self.__cnx()
        cur = cnx.cursor(True)
        cur.execute('SET @@local.net_read_timeout=3600;')
        cur.execute('SHOW DATABASES LIKE "moirai"')
        if len(list(cur)) > 0:
            return
        cur.execute(
            'CREATE SCHEMA IF NOT EXISTS `moirai` DEFAULT CHARACTER SET utf8')
        cur.execute('USE moirai')
        cur.execute(
            '''CREATE TABLE IF NOT EXISTS `moirai`.`settings`
                (`id` INT NOT NULL AUTO_INCREMENT,
                `value` LONGTEXT NULL,
                `key` VARCHAR(100) NOT NULL,
                PRIMARY KEY (`id`), UNIQUE INDEX `key_UNIQUE` (`id` ASC),
                UNIQUE INDEX `key_idx` (`key` ASC))
                ENGINE = InnoDB DEFAULT CHARACTER SET = utf8
            ''')
        cur.execute(
            '''CREATE TABLE IF NOT EXISTS `moirai`.`graphs`
                (`id` INT NOT NULL AUTO_INCREMENT,
                `name` VARCHAR(100) NOT NULL, `date` DATETIME NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE INDEX `id_UNIQUE` (`id` ASC),
                INDEX `date_idx` (`date` ASC),
                INDEX `name_idx` (`name` ASC))
                ENGINE = InnoDB DEFAULT CHARACTER SET = utf8
            ''')
        cur.execute(
            '''CREATE TABLE IF NOT EXISTS `moirai`.`graphs_data`
                (`id` INT NOT NULL AUTO_INCREMENT,
                `sensor` VARCHAR(100) NOT NULL, `value` DOUBLE NOT NULL,
                `time` FLOAT NOT NULL, `graph` INT NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE INDEX `id_UNIQUE` (`id` ASC),
                INDEX `graph_idx` (`graph` ASC),
                FOREIGN KEY (graph)
                    REFERENCES graphs(id)
                    ON DELETE CASCADE)
                    ENGINE = InnoDB DEFAULT CHARACTER SET = utf8
            ''')
        cur.execute(
            '''INSERT INTO moirai.settings (`key`, `value`)
                VALUES ("version", "1.0")
                ON DUPLICATE KEY UPDATE `value`="1.0"
            ''')
        cur.close()
        cnx.close()

    def __migrate(self):
        cnx = self.__cnx()
        cur = cnx.cursor(True)

        query = 'SELECT `value` FROM `moirai`.`settings` WHERE `key`="version"'
        cur.execute(query)
        version = list(cur)
        if len(version) == 0:
            cur.execute('USE moirai')
            cur.execute('''CREATE TABLE IF NOT EXISTS `moirai`.`graphs`
                       (`id` INT NOT NULL AUTO_INCREMENT,
                       `name` VARCHAR(100) NOT NULL, `date` DATETIME NOT NULL,
                       PRIMARY KEY (`id`),
                       UNIQUE INDEX `id_UNIQUE` (`id` ASC),
                       INDEX `date_idx` (`date` ASC),
                       INDEX `name_idx` (`name` ASC))
                       ENGINE = InnoDB DEFAULT CHARACTER SET = utf8''')
            cur.execute('''CREATE TABLE IF NOT EXISTS `moirai`.`graphs_data`
                       (`id` INT NOT NULL AUTO_INCREMENT,
                       `sensor` VARCHAR(100) NOT NULL, `value` DOUBLE NOT NULL,
                       `time` FLOAT NOT NULL, `graph` INT NOT NULL,
                       PRIMARY KEY (`id`),
                       UNIQUE INDEX `id_UNIQUE` (`id` ASC),
                       INDEX `graph_idx` (`graph` ASC),
                       FOREIGN KEY (graph)
                        REFERENCES graphs(id)
                        ON DELETE CASCADE)
                       ENGINE = InnoDB DEFAULT CHARACTER SET = utf8''')

            q = 'SELECT DISTINCT test, start_time FROM moirai.sensor_values'
            cur.execute(q)
            graphs = set(cur)
            query = '''INSERT INTO `moirai`.`graphs` (`name`,`date`)
                              VALUE (%s, %s)'''
            cur.executemany(query, graphs)
            for name, date in graphs:
                query = '''SELECT `id` FROM `moirai`.`graphs`
                                WHERE `name`=%s AND `date`=%s'''
                cur.execute(query, (name, date))
                rowid = list(cur)[0][0]
                query = '''INSERT INTO `moirai`.`graphs_data`
                                (`sensor`, `time`, `value`, `graph`)
                                SELECT `sensor`, `time`, `value`, %s as `graph`
                                FROM `moirai`.`sensor_values`
                                WHERE `test`=%s AND `start_time`=%s
                                ORDER BY `time`'''
                cur.execute(query, (rowid, name, date))

            cur.execute('DROP TABLE IF EXISTS `moirai`.`sensor_values`')
            cur.execute('''INSERT INTO `moirai`.`settings` (`key`, `value`)
                                VALUES ("version", "1.0")
                                ON DUPLICATE KEY UPDATE `value`="1.0"''')
        cur.close()
        cnx.close()
