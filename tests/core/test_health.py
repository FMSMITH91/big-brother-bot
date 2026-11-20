# -*- coding: utf-8 -*-
"""
The health file (linuxgsm-panel request 2): B3's state as JSON, atomically rewritten, free of secrets and IPs.
"""
import json
import logging
import os
import shutil
import stat
import tempfile
import time
import unittest
from unittest.mock import Mock

import b3
import b3.health
from b3.health import Health, sanitize


class FakeClient(object):
    def __init__(self, bot=False):
        self.bot = bot


def console(password='rconsecret', dsn='mysql://b3:dbsecret@db.example:3306/b3'):
    c = Mock()
    c.log = logging.getLogger('test_health_%s' % time.time())
    c.log.setLevel(logging.DEBUG)
    c._rconPassword = password
    c.gameName = 'et'
    c.config.get.side_effect = lambda s, o: dsn if (s, o) == ('b3', 'database') else ''
    c.clients.getList.return_value = [FakeClient(), FakeClient(), FakeClient(bot=True)]
    c.storage.status.return_value = True
    return c


class HealthCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = os.path.join(self.dir, 'health.json')
        self.console = console()
        self.health = Health(self.console, self.path, interval=60)
        self.addCleanup(self.health.stop)

    def read(self):
        self.health.write()
        with open(self.path) as f:
            return json.load(f)


class Test_document(HealthCase):

    def test_starting(self):
        doc = self.read()
        self.assertEqual(1, doc['schema'])
        self.assertEqual('starting', doc['state'])
        self.assertFalse(doc['healthy'])
        self.assertEqual('B3 is starting', doc['reason'])
        self.assertEqual(b3.__version__, doc['b3']['version'])
        self.assertEqual('et', doc['b3']['parser'])
        self.assertEqual({'humans': 2, 'bots': 1}, doc['players'])

    def test_healthy_when_running_and_reading(self):
        self.health.state = 'running'
        self.health.record_read()
        self.health.record_line()
        self.health.record_rcon(reply='map: oasis\nnum score ping')
        doc = self.read()
        self.assertTrue(doc['healthy'], doc)
        self.assertIsNone(doc['reason'])
        self.assertTrue(doc['rcon']['ok'])
        self.assertEqual(1, doc['game_log']['lines_parsed'])
        self.assertTrue(doc['written_at'].endswith('Z'))

    def test_log_not_read(self):
        self.health.state = 'running'
        doc = self.read()
        self.assertEqual('the game log is not being read', doc['reason'])
        self.health.last_read_at = time.time() - 300
        self.assertFalse(self.read()['game_log']['ok'])

    def test_bad_rcon_password(self):
        self.health.state = 'running'
        self.health.record_read()
        self.health.record_rcon(reply='Bad rconpassword.\n')
        doc = self.read()
        self.assertFalse(doc['healthy'])
        self.assertEqual('RCON: bad RCON password', doc['reason'])
        self.assertFalse(doc['rcon']['ok'])
        # an empty reply (say, kick...) does not change the verdict; a real reply does
        self.health.record_rcon(reply='')
        self.assertFalse(self.read()['rcon']['ok'])
        self.health.record_rcon(reply='map: oasis')
        self.assertTrue(self.read()['healthy'])

    def test_database_lost(self):
        self.health.state = 'running'
        self.health.record_read()
        self.console.storage.status.return_value = False
        self.assertEqual('the database connection is lost', self.read()['reason'])

    def test_last_error_from_the_log(self):
        self.console.log.error('Could not parse line from 203.0.113.9:27960')
        self.console.log.warning('just a warning')
        doc = self.read()
        self.assertEqual('Could not parse line from <ip>', doc['last_error']['message'])

    def test_stopped_with_exit_code(self):
        self.health.stop(233)
        with open(self.path) as f:
            doc = json.load(f)
        self.assertEqual('stopped', doc['state'])
        self.assertEqual(233, doc['exit_code'])
        self.assertEqual('B3 is stopped', doc['reason'])


class Test_privacy(HealthCase):

    def test_no_secret_or_ip_in_the_file(self):
        self.console.log.error('rcon to 192.0.2.10:27960 with rconsecret failed')
        self.health.record_rcon(error=OSError('mysql://b3:dbsecret@db.example/b3 refused from 2001:db8::1'))
        self.console.log.critical('connecting to fe80:0:0:0:0:0:0:1 and 10.0.0.1')
        with open(self.path, 'w'):
            pass
        self.health.write()
        with open(self.path) as f:
            text = f.read()
        for leak in ('rconsecret', 'dbsecret', '192.0.2.10', '2001:db8::1', 'fe80:0:0', '10.0.0.1'):
            self.assertNotIn(leak, text)
        self.assertIn('<ip>', text)

    def test_times_are_not_taken_for_ipv6(self):
        self.assertEqual('at 17:27:49 ok', sanitize('at 17:27:49 ok'))
        self.assertEqual('<ip> and <ip>', sanitize('::1 and 2001:db8:0:1:2:3:4:5'))

    def test_one_short_line(self):
        self.assertEqual('a b', sanitize('a\n  b'))
        self.assertEqual(300, len(sanitize('x' * 1000)))


class Test_file(HealthCase):

    def test_atomic_and_mode(self):
        old = os.umask(0o022)
        try:
            self.health.write()
            self.assertEqual(0o640, stat.S_IMODE(os.stat(self.path).st_mode))
            self.health.mode = 0o644
            self.health.write()
            self.assertEqual(0o644, stat.S_IMODE(os.stat(self.path).st_mode))
        finally:
            os.umask(old)
        self.assertEqual(['health.json'], os.listdir(self.dir))  # no temporary file left behind

    def test_parse_mode(self):
        self.assertEqual(0o640, b3.health.parse_mode('640'))
        self.assertEqual(0o644, b3.health.parse_mode('0o644'))
        for bad in ('755', 'rw', '', '1777'):
            self.assertRaises(ValueError, b3.health.parse_mode, bad)

    def test_unwritable_folder_only_warns(self):
        health = Health(self.console, os.path.join(self.dir, 'missing', 'health.json'))
        health.write()  # must not raise
        self.assertTrue(self.console.warning.called)

    def test_thread_rewrites(self):
        self.health.interval = 0.05
        self.health.start()
        first = os.stat(self.path).st_mtime_ns
        deadline = time.time() + 5
        while os.stat(self.path).st_mtime_ns == first and time.time() < deadline:
            time.sleep(0.05)
        self.assertNotEqual(first, os.stat(self.path).st_mtime_ns)


class Test_from_config(unittest.TestCase):

    def make(self, **options):
        c = console()
        c.config.has_option.side_effect = lambda s, o: s == 'b3' and o in options
        c.config.get.side_effect = lambda s, o: options[o]
        return c

    def test_off(self):
        self.assertIsNone(b3.health.from_config(self.make(health_file='off')))

    def test_path_and_interval(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        h = b3.health.from_config(self.make(health_file=os.path.join(d, 'h.json'), health_interval='1'))
        self.addCleanup(h.stop)
        self.assertEqual(b3.health.MIN_INTERVAL, h.interval)
        self.assertTrue(os.path.isfile(os.path.join(d, 'h.json')))
