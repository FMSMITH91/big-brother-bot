# -*- coding: utf-8 -*-

# ################################################################### #
#                                                                     #
#  BigBrotherBot(B3) (www.bigbrotherbot.net)                          #
#                                                                     #
#  This program is free software; you can redistribute it and/or      #
#  modify it under the terms of the GNU General Public License        #
#  as published by the Free Software Foundation; either version 2     #
#  of the License, or (at your option) any later version.             #
#                                                                     #
# ################################################################### #
"""
End-to-end smoke test: run the real bot (b3_run.py, in its own process) against a fake Urban Terror 4.3 server
answering UDP rcon, feed it game log lines and check what it sends back to the server and stores in its
(SQLite) database. Unlike the unit tests, nothing inside B3 is mocked.

Run it on its own: python -m pytest tests/functional
"""

import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RCON_PASSWORD = 'Rc0n-7d3e9-Pw'  # distinctive, so the leak checks below cannot match by chance
HEADER = b'\xff\xff\xff\xff'
CVARS = {
    'mapname': 'ut4_turnpike', 'g_gametype': '4', 'sv_hostname': 'Test Server', 'fs_game': 'q3ut4',
    'version': 'ioq3 1.35 urt 4.3.4', 'gamename': 'q3urt43', 'auth_enable': '0', 'auth': '0',
    'g_maxGameClients': '0', 'sv_maxclients': '16', 'g_mapcycle': 'mapcycle.txt', 'sv_joinmessage': '',
    'timelimit': '20', 'fraglimit': '0', 'capturelimit': '0', 'g_nextmap': 'ut4_casa', 'g_matchmode': '0',
    'auth_owners': '', 'sv_privateClients': '0', 'g_allowvote': '0', 'g_followstrict': '0',
    'g_teamnamered': 'Red', 'g_teamnameblue': 'Blue', 'g_swaproles': '0', 'g_maxrounds': '0', 'g_gear': '0',
    'g_respawndelay': '5', 'g_friendlyfire': '1',
}
PLAYER = 'Pl\u00e4yer'  # non-ASCII on purpose: the server and its log use latin-1
GUID = 'A' * 32


class FakeUrtServer(object):
    """
    Minimal Urban Terror 4.3 server answering UDP rcon and recording every rcon command it receives.
    """

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', 0))
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.commands = []
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self.serve, name='fake-urt', daemon=True)
        self.thread.start()

    def stop(self):
        self._stop.set()
        self.thread.join(5)
        self.sock.close()

    def reply(self, command):
        name = command.split(' ')[0].strip('"')
        if command == 'status':
            return ('map: ut4_turnpike\nnum score ping name            lastmsg address               qport rate\n'
                    '--- ----- ---- --------------- ------- --------------------- ----- -----\n'
                    '  0     5   48 %s^7              0 127.0.0.1:27961       12345 25000\n' % PLAYER)
        if command == 'players':
            return ('Map: ut4_turnpike\nPlayers: 1\nGameType: CTF\nScores: R:0 B:0\nMatchMode: OFF\n'
                    'WarmupPhase: NO\nGameTime: 00:01:00\n0:%s^7 RED k:5 d:0 ping:48 127.0.0.1:27961\n' % PLAYER)
        if name in CVARS and ' ' not in command:
            return '"%s" is:"%s^7" default:"x^7"\n' % (name, CVARS[name])
        if command.startswith('dumpuser'):
            return ('userinfo\n--------\nip                  127.0.0.1:27961\nname                %s\n'
                    'cl_guid             %s\nauthl               \n' % (PLAYER, GUID))
        return ''

    def serve(self):
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            if not data.startswith(HEADER):
                continue
            body = data[4:].decode('latin-1').rstrip('\n')
            m = re.match(r'rcon "([^"]*)" (.*)$', body, re.S)
            if not m:
                self.sock.sendto(HEADER + b'infoResponse\n\\mapname\\ut4_turnpike\n', addr)
                continue
            if m.group(1) != RCON_PASSWORD:
                self.sock.sendto(HEADER + b'print\nBad rconpassword.\n', addr)
                continue
            command = m.group(2).strip()
            self.commands.append(command)
            self.sock.sendto(HEADER + b'print\n' + self.reply(command).encode('latin-1'), addr)


class Test_urt_smoke(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server = FakeUrtServer()
        self.addCleanup(self.server.stop)
        d = self.tmp.name
        self.db = os.path.join(d, 'b3.db')
        self.game_log = os.path.join(d, 'games.log')
        self.b3_log = os.path.join(d, 'b3.log')
        open(self.game_log, 'wb').close()
        self.config = os.path.join(d, 'b3.ini')
        with open(self.config, 'w', encoding='utf-8') as f:
            f.write("""[b3]
parser: iourt43
database: sqlite://%(db)s
bot_name: b3
bot_prefix: ^0(^2b3^0)^7:
time_format: %%I:%%M%%p %%Z %%m/%%d/%%y
time_zone: UTC
log_level: 1
health_interval: 5
logfile: %(b3_log)s
disabled_plugins:
external_plugins_dir: @b3/extplugins
[server]
rcon_password: %(password)s
port: %(port)s
game_log: %(game_log)s
public_ip: 127.0.0.1
rcon_ip: 127.0.0.1
punkbuster: off
delay: 0.1
lines_per_second: 50
encoding: latin-1
[update]
channel: skip
[messages]
kicked_by: $clientname^7 was kicked by $adminname^7 $reason
kicked: $clientname^7 was kicked $reason
banned_by: $clientname^7 was banned by $adminname^7 $reason
banned: $clientname^7 was banned $reason
temp_banned_by: $clientname^7 was temp banned by $adminname^7 for $banduration^7 $reason
temp_banned: $clientname^7 was temp banned for $banduration^7 $reason
unbanned_by: $clientname^7 was un-banned by $adminname^7 $reason
unbanned: $clientname^7 was un-banned^7 $reason
[plugins]
admin: @b3/conf/plugin_admin.ini
xlrstats: @b3/conf/plugin_xlrstats.ini
""" % {'db': self.db, 'b3_log': self.b3_log, 'password': RCON_PASSWORD, 'port': self.server.port,
       'game_log': self.game_log})
        self.stdout_path = os.path.join(d, 'stdout.txt')
        self.stdout = open(self.stdout_path, 'w')
        self.addCleanup(self.stdout.close)
        self.process = subprocess.Popen([sys.executable, '-W', 'ignore', os.path.join(ROOT, 'b3_run.py'),
                                         '-c', self.config], cwd=ROOT, stdout=self.stdout,
                                        stderr=subprocess.STDOUT, env=dict(os.environ, HOME=d))
        self.addCleanup(self.stop_bot)

    def stop_bot(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(10)

    def output(self):
        with open(self.stdout_path, encoding='utf-8', errors='replace') as f:
            return f.read()

    def wait_for(self, condition, timeout, what):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if condition():
                return
            if self.process.poll() is not None:
                self.fail('B3 exited (code %s) while waiting for %s:\n%s' % (self.process.returncode, what,
                                                                             self.output()))
            time.sleep(0.2)
        self.fail('timed out waiting for %s\n--- stdout ---\n%s\n--- rcon commands received ---\n%s\n'
                  '--- end of b3.log ---\n%s' % (what, self.output(), '\n'.join(self.server.commands[-30:]),
                                                 self.b3_log_tail()))

    def b3_log_tail(self, lines=80):
        try:
            with open(self.b3_log, encoding='utf-8', errors='replace') as f:
                return ''.join(f.readlines()[-lines:])
        except OSError:
            return '(no b3.log)'

    def log(self, *lines):
        with open(self.game_log, 'ab') as f:
            for line in lines:
                f.write(('  0:01 %s\n' % line).encode('latin-1'))

    def tells(self):
        return [c for c in self.server.commands if c.startswith('tell 0 ')]

    def test_bot_answers_commands_and_stores_the_player(self):
        self.wait_for(lambda: 'Startup complete' in self.output(), 60, 'B3 to start')

        self.log('InitGame: \\sv_allowdownload\\0\\g_matchmode\\0\\g_gametype\\4\\mapname\\ut4_turnpike',
                 'ClientConnect: 0',
                 'ClientUserinfo: 0 \\ip\\127.0.0.1:27961\\name\\%s\\racered\\2\\raceblue\\2\\rate\\25000'
                 '\\cl_guid\\%s\\gear\\GZAAVWT\\authl\\' % (PLAYER, GUID),
                 'ClientUserinfoChanged: 0 n\\%s\\t\\1\\r\\0\\tl\\0\\f0\\\\f1\\\\f2\\\\a0\\0\\a1\\0\\a2\\0' % PLAYER,
                 'ClientBegin: 0')
        # commands are refused until the player is authenticated (deny by default): the iourt43 auth-whois retries can
        # take several seconds, so wait for it as a player in game would
        self.wait_for(lambda: 'Client authorized' in self.b3_log_tail(400), 60, 'the player to be authorized')
        self.log('say: 0 %s: !help' % PLAYER,
                 'say: 0 %s: !iamgod' % PLAYER,
                 'say: 0 %s: !leveltest' % PLAYER)

        self.wait_for(lambda: any('Super Admin' in t and 'since' in t for t in self.tells()), 60,
                      'the !leveltest reply')
        tells = self.tells()
        self.assertTrue(any('Available commands' in t for t in tells), tells)
        self.assertTrue(any('You are now a ^2Super Admin' in t for t in tells), tells)

        # the health file next to b3.ini (linuxgsm-panel request 2): running and healthy, then stopped with status 0
        health_path = os.path.join(os.path.dirname(self.config), 'health.json')
        self.wait_for(lambda: json.load(open(health_path))['players']['humans'] == 1, 30, 'health.json to show the player')
        health = json.load(open(health_path))
        self.assertEqual('running', health['state'], health)
        self.assertTrue(health['healthy'], health)
        self.assertEqual({'humans': 1, 'bots': 0}, health['players'])
        self.assertNotIn(RCON_PASSWORD, open(health_path).read())
        self.assertNotIn('127.0.0.1', open(health_path).read())

        self.stop_bot()
        health = json.load(open(health_path))
        self.assertEqual(('stopped', 0), (health['state'], health['exit_code']))
        db = sqlite3.connect(self.db)
        self.addCleanup(db.close)
        rows = db.execute('SELECT name, group_bits FROM clients WHERE guid = ?', (GUID,)).fetchall()
        self.assertEqual([(PLAYER, 128)], rows)  # stored with its non-ASCII name, as superadmin

        with open(self.b3_log, encoding='utf-8', errors='replace') as f:
            b3_log = f.read()
        self.assertNotIn('Traceback', b3_log)
        # the RCON password never reaches b3.log or the console, even at the most verbose log level (it is in every
        # RCON packet B3 sends)
        self.assertIn('RCON sending', b3_log)
        self.assertNotIn(RCON_PASSWORD, b3_log)
        self.assertNotIn(RCON_PASSWORD, self.output())


if __name__ == '__main__':
    unittest.main()
