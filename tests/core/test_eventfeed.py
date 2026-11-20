# -*- coding: utf-8 -*-
"""
events.jsonl (linuxgsm-panel request 6): one JSON line per penalty and admin command, capped, without IPs, guids or
passwords.
"""
import json
import os
import shutil
import stat
import tempfile

from b3.eventfeed import EventFeed
from tests import B3TestCase


class Test_eventfeed(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = os.path.join(self.dir, 'events.jsonl')
        self.console.eventFeed = EventFeed(self.console, self.path)
        self.console.startup()
        self.joe = self.console.clients.newClient('3', name='^1Joe', guid='AAAABBBBCCCCDDDD', ip='203.0.113.7')
        self.joe.id = 12
        self.admin = self.console.clients.newClient('4', name='Admin', guid='EEEEFFFF00001111', ip='198.51.100.2')
        self.admin.id = 1

    def lines(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding='utf-8') as f:
            return [json.loads(line) for line in f]

    def queue(self, key, data, client):
        self.console.queueEvent(self.console.getEvent(key, data=data, client=client))

    def test_ban(self):
        self.queue('EVT_CLIENT_BAN', {'reason': '^3cheating', 'admin': self.admin}, self.joe)
        (line,) = self.lines()
        self.assertEqual('ban', line['event'])
        self.assertEqual({'id': 12, 'cid': '3', 'name': 'Joe'}, line['target'])
        self.assertEqual({'id': 1, 'cid': '4', 'name': 'Admin'}, line['admin'])
        self.assertEqual('cheating', line['reason'])
        self.assertTrue(line['time'].endswith('Z'))
        self.assertEqual(1, line['schema'])

    def test_tempban_kick_warn_unban(self):
        self.queue('EVT_CLIENT_BAN_TEMP', {'reason': 'spam', 'duration': '2h', 'admin': None}, self.joe)
        self.queue('EVT_CLIENT_KICK', {'reason': 'afk', 'admin': self.admin}, self.joe)
        self.queue('EVT_CLIENT_WARN', {'reason': 'language', 'duration': 60, 'admin': self.admin, 'data': ''}, self.joe)
        self.queue('EVT_CLIENT_UNBAN', 'appeal accepted', self.joe)
        self.queue('EVT_CLIENT_UNBAN', self.admin, self.joe)  # iourt41 passes the admin as the data
        lines = self.lines()
        self.assertEqual(['tempban', 'kick', 'warn', 'unban', 'unban'], [l['event'] for l in lines])
        self.assertEqual(120, lines[0]['duration_minutes'])
        self.assertIsNone(lines[0]['admin'])
        self.assertEqual(60, lines[2]['duration_minutes'])
        self.assertEqual('appeal accepted', lines[3]['reason'])
        self.assertEqual(1, lines[4]['admin']['id'])

    def test_admin_command_and_secret_arguments(self):
        class Command(object):
            def __init__(self, name):
                self.command = name
        self.console.createEvent('EVT_ADMIN_COMMAND', 'Admin Command')
        self.queue('EVT_ADMIN_COMMAND', (Command('ban'), 'joe cheating', None), self.admin)
        self.queue('EVT_ADMIN_COMMAND', (Command('setpassword'), 'hunter2', None), self.admin)
        self.queue('EVT_ADMIN_COMMAND', (Command('login'), 'hunter2', None), self.admin)
        lines = self.lines()
        self.assertEqual(('ban', 'joe cheating'), (lines[0]['command'], lines[0]['args']))
        self.assertEqual([None, None], [lines[1]['args'], lines[2]['args']])
        self.assertNotIn('hunter2', open(self.path).read())

    def test_args_only_for_allow_listed_commands(self):
        class Command(object):
            def __init__(self, name):
                self.command = name
        self.console.createEvent('EVT_ADMIN_COMMAND', 'Admin Command')
        for name, args in (('rcon', 'rconpassword newsecret'), ('pacvar', 'sv_password x'), ('makereg', 'joe'),
                           ('register', 'pw'), ('somepluginthing', 'whatever')):
            self.queue('EVT_ADMIN_COMMAND', (Command(name), args, None), self.admin)
        self.queue('EVT_ADMIN_COMMAND', (Command('TempBan'), 'joe 1h spam', None), self.admin)
        lines = self.lines()
        self.assertEqual([None] * 5, [l['args'] for l in lines[:5]])
        self.assertEqual('joe 1h spam', lines[5]['args'])

    def test_configured_passwords_are_scrubbed(self):
        self.console._rconPassword = 'Rc0nS3cret'
        self.queue('EVT_CLIENT_KICK', {'reason': 'typed Rc0nS3cret in chat', 'admin': None}, self.joe)
        self.console.eventFeed.control('kick', {'cid': '3', 'reason': 'leaked Rc0nS3cret'}, True)
        text = open(self.path).read()
        self.assertNotIn('Rc0nS3cret', text)
        self.assertEqual(2, text.count('******'))

    def test_no_ip_or_guid(self):
        self.queue('EVT_CLIENT_BAN', {'reason': 'x', 'admin': self.admin}, self.joe)
        text = open(self.path).read()
        for leak in ('203.0.113.7', '198.51.100.2', 'AAAABBBBCCCCDDDD', 'EEEEFFFF00001111'):
            self.assertNotIn(leak, text)

    def test_other_events_ignored(self):
        self.queue('EVT_CLIENT_SAY', 'hello', self.joe)
        self.assertEqual([], self.lines())

    def test_rotation_and_mode(self):
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)
        feed = self.console.eventFeed
        feed.max_size = 400
        for i in range(10):
            self.queue('EVT_CLIENT_KICK', {'reason': 'reason %s' % i, 'admin': None}, self.joe)
        self.assertTrue(os.path.exists(self.path + '.1'))
        self.assertLessEqual(os.path.getsize(self.path), 400)
        self.assertEqual(0o640, stat.S_IMODE(os.stat(self.path).st_mode))
        reasons = [l['reason'] for l in self.lines()]
        self.assertEqual('reason 9', reasons[-1])

    def test_unwritable_only_warns(self):
        self.console.eventFeed = EventFeed(self.console, os.path.join(self.dir, 'missing', 'events.jsonl'))
        self.queue('EVT_CLIENT_KICK', {'reason': 'x', 'admin': None}, self.joe)  # must not raise
