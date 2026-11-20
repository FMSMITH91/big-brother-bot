# -*- coding: utf-8 -*-
"""
The local control socket (linuxgsm-panel request 5): Unix socket only, mode 0600, own uid only, an allow-listed command
set with strict argument validation, every request logged.
"""
import json
import os
import socket
import stat
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch

from b3.control import ControlServer, Refused, parse_request, MAX_REQUEST
from b3.eventfeed import EventFeed
from tests import B3TestCase


class Test_parse_request(unittest.TestCase):

    def ok(self, req):
        return parse_request(json.dumps(req).encode())

    def refused(self, raw, error):
        if not isinstance(raw, bytes):
            raw = json.dumps(raw).encode()
        with self.assertRaises(Refused) as ctx:
            parse_request(raw)
        self.assertEqual(error, ctx.exception.error, ctx.exception.message)

    def test_valid(self):
        self.assertEqual((7, 'unban', {'client_id': 12, 'reason': 'appeal'}),
                         self.ok({'id': 7, 'cmd': 'unban', 'args': {'client_id': 12, 'reason': 'appeal'}}))
        self.assertEqual((None, 'ping', {}), self.ok({'cmd': 'ping'}))
        self.assertEqual(('a', 'kick', {'cid': '3'}), self.ok({'id': 'a', 'cmd': 'kick', 'args': {'cid': '3'}}))

    def test_allow_list(self):
        self.refused({'cmd': 'rcon', 'args': {'line': 'quit'}}, 'unknown_command')
        self.refused({'cmd': '__init__'}, 'unknown_command')
        self.refused({'cmd': ['ping']}, 'unknown_command')

    def test_unknown_fields(self):
        self.refused({'cmd': 'ping', 'admin': True}, 'invalid_request')
        self.refused({'cmd': 'unban', 'args': {'client_id': 1, 'silent': False}}, 'invalid_args')

    def test_types(self):
        self.refused({'cmd': 'unban', 'args': {'client_id': '12'}}, 'invalid_args')
        self.refused({'cmd': 'unban', 'args': {'client_id': True}}, 'invalid_args')
        self.refused({'cmd': 'unban', 'args': {'client_id': 0}}, 'invalid_args')
        self.refused({'cmd': 'unban', 'args': {'client_id': 2 ** 31}}, 'invalid_args')
        self.refused({'cmd': 'kick', 'args': {'cid': 3}}, 'invalid_args')
        self.refused({'cmd': 'kick', 'args': {'cid': '3; quit'}}, 'invalid_args')
        self.refused({'cmd': 'kick', 'args': {'cid': '1234'}}, 'invalid_args')
        self.refused({'cmd': 'ping', 'args': []}, 'invalid_args')
        self.refused({'cmd': 'ping', 'id': True}, 'invalid_request')
        self.refused({'cmd': 'ping', 'id': 'x' * 65}, 'invalid_request')

    def test_required(self):
        self.refused({'cmd': 'unban'}, 'invalid_args')
        self.refused({'cmd': 'warn', 'args': {'cid': '3'}}, 'invalid_args')
        self.refused({'cmd': 'warn', 'args': {'cid': '3', 'reason': ''}}, 'invalid_args')

    def test_reason(self):
        self.refused({'cmd': 'kick', 'args': {'cid': '3', 'reason': 'x' * 101}}, 'invalid_args')
        self.refused({'cmd': 'kick', 'args': {'cid': '3', 'reason': 'a\nsay hacked'}}, 'invalid_args')
        self.refused({'cmd': 'kick', 'args': {'cid': '3', 'reason': '^1red'}}, 'invalid_args')
        self.refused({'cmd': 'kick', 'args': {'cid': '3', 'reason': 5}}, 'invalid_args')
        self.assertEqual('Non-ASCII é ok', self.ok({'cmd': 'kick', 'args': {'cid': '3', 'reason': 'Non-ASCII é ok'}})[2]['reason'])

    def test_malformed(self):
        self.refused(b'not json', 'bad_json')
        self.refused(b'[1, 2]', 'bad_json')
        self.refused(b'\xff\xfe', 'bad_json')
        self.refused(b'{"cmd": "ping", "x": "' + b'a' * MAX_REQUEST + b'"}', 'too_large')


@unittest.skipUnless(hasattr(socket, 'AF_UNIX') and sys.platform != 'win32', 'Unix sockets only')
class Test_server(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        # AF_UNIX paths are short (108 bytes): use a short temporary folder
        self.dir = tempfile.mkdtemp(prefix='b3c')
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = os.path.join(self.dir, 'b3.sock')
        self.feed_path = os.path.join(self.dir, 'events.jsonl')
        self.console.eventFeed = EventFeed(self.console, self.feed_path)
        self.console.startup()
        self.joe = self.console.clients.newClient('3', name='Joe', guid='AAAABBBBCCCCDDDD', ip='203.0.113.7')
        self.server = ControlServer(self.console, self.path)
        self.assertTrue(self.server.start())
        self.addCleanup(self.server.stop)

    def call(self, req, raw=None):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect(self.path)
        s.sendall(raw if raw is not None else (json.dumps(req) + '\n').encode())
        data = b''
        while not data.endswith(b'\n'):
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        s.close()
        return json.loads(data)

    def feed(self):
        with open(self.feed_path) as f:
            return [json.loads(l) for l in f if '"control_command"' in l]

    def test_socket_is_private(self):
        st = os.stat(self.path)
        self.assertTrue(stat.S_ISSOCK(st.st_mode))
        self.assertEqual(0o600, stat.S_IMODE(st.st_mode))

    def test_ping(self):
        reply = self.call({'id': 1, 'cmd': 'ping'})
        self.assertEqual((1, True), (reply['id'], reply['ok']))
        self.assertIn('version', reply['result'])

    def test_refused_request_is_answered_and_logged(self):
        reply = self.call({'cmd': 'rcon', 'args': {'line': 'quit'}})
        self.assertEqual((False, 'unknown_command'), (reply['ok'], reply['error']))
        (line,) = self.feed()
        self.assertEqual((False, 'unknown_command'), (line['ok'], line['error']))

    def test_kick(self):
        reply = self.call({'id': 2, 'cmd': 'kick', 'args': {'cid': '3', 'reason': 'afk'}})
        self.assertTrue(reply['ok'], reply)
        self.assertIsNone(self.console.clients.getByCID('3'))  # FakeConsole.kick disconnects
        self.assertEqual(('kick', {'cid': '3', 'reason': 'afk'}, True),
                         (self.feed()[0]['command'], self.feed()[0]['args'], self.feed()[0]['ok']))

    def test_kick_unknown_slot(self):
        reply = self.call({'cmd': 'kick', 'args': {'cid': '9'}})
        self.assertEqual('not_found', reply['error'])

    def test_warn(self):
        reply = self.call({'cmd': 'warn', 'args': {'cid': '3', 'reason': 'language'}})
        self.assertTrue(reply['ok'], reply)
        self.assertEqual(1, self.joe.numWarnings)

    def test_unban_and_list_penalties(self):
        self.joe.save()
        self.joe.tempban('spam', duration='1h')
        listed = self.call({'cmd': 'list_penalties', 'args': {'client_id': self.joe.id}})
        self.assertTrue(listed['ok'], listed)
        self.assertEqual(['TempBan'], [p['type'] for p in listed['result']['penalties']])
        reply = self.call({'cmd': 'unban', 'args': {'client_id': self.joe.id, 'reason': 'appeal'}})
        self.assertEqual({'client_id': self.joe.id, 'bans_lifted': 1}, reply['result'])
        listed = self.call({'cmd': 'list_penalties', 'args': {'client_id': self.joe.id}})
        self.assertEqual([], listed['result']['penalties'])

    def test_unban_unknown_client(self):
        self.assertEqual('not_found', self.call({'cmd': 'unban', 'args': {'client_id': 999}})['error'])

    def test_other_uid_is_refused(self):
        with patch('b3.control.peer_uid', return_value=os.getuid() + 1):
            reply = self.call({'cmd': 'ping'})
        self.assertEqual('forbidden', reply['error'])
        self.assertEqual('forbidden', self.feed()[0]['error'])

    def test_oversized_request(self):
        reply = self.call(None, raw=b'{"cmd": "ping", "pad": "' + b'a' * (MAX_REQUEST + 10) + b'"}\n')
        self.assertEqual('too_large', reply['error'])

    def test_stop_removes_socket(self):
        self.server.stop()
        self.assertFalse(os.path.exists(self.path))

    def test_stale_socket_replaced_but_not_a_regular_file(self):
        self.server.stop()
        stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale.bind(self.path)
        stale.close()
        server = ControlServer(self.console, self.path)
        self.assertTrue(server.start())
        server.stop()
        with open(self.path, 'w') as f:
            f.write('keep me')
        self.assertFalse(ControlServer(self.console, self.path).start())
        with open(self.path) as f:
            self.assertEqual('keep me', f.read())
        os.unlink(self.path)
