# -*- coding: utf-8 -*-
"""
b3 --check-config (linuxgsm-panel request): validate b3.ini and plugin configs without connecting, one ERROR line per
problem, exit status 230 (b3.exitcodes.CONFIG) or 0.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import b3
import b3.exitcodes
from b3.checkconfig import check_config, main

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GOOD = """\
[b3]
parser: et
database: sqlite://:memory:
bot_name: b3
bot_prefix: ^0(^2b3^0)^7:
time_format: %I:%M%p %Z %m/%d/%y
log_level: 9
logfile: b3.log
[server]
rcon_password: secret
port: 27960
game_log: games.log
public_ip: 127.0.0.1
[plugins]
admin: @b3/conf/plugin_admin.ini
welcome: @conf/plugin_welcome.ini
"""


class CheckConfigCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(setattr, b3, 'confdir', b3.confdir)
        shutil.copy(os.path.join(ROOT, 'b3', 'conf', 'plugin_welcome.ini'), self.dir)

    def write(self, text, name='b3.ini'):
        path = os.path.join(self.dir, name)
        with open(path, 'w') as f:
            f.write(text)
        return path


class Test_check_config(CheckConfigCase):

    def test_valid(self):
        self.assertEqual([], check_config(self.write(GOOD)))

    def test_file_not_found(self):
        self.assertIn('not found', check_config(os.path.join(self.dir, 'nope.ini'))[0])

    def test_unreadable_ini(self):
        self.assertIn('cannot read', check_config(self.write('this is not an ini file\n'))[0])

    def test_bad_parser(self):
        self.assertEqual(['invalid parser specified in b3::parser (nope)'],
                         check_config(self.write(GOOD.replace('parser: et', 'parser: nope'))))

    def test_bad_numbers(self):
        problems = check_config(self.write(GOOD.replace('port: 27960', 'port: abc').replace('log_level: 9', 'log_level: x')))
        self.assertIn("server::port must be a port number (found 'abc')", problems)
        self.assertIn("b3::log_level must be a number (found 'x')", problems)

    def test_settings_b3_needs_at_startup(self):
        for line in ('bot_prefix: ^0(^2b3^0)^7:\n', 'logfile: b3.log\n', 'port: 27960\n', 'public_ip: 127.0.0.1\n',
                     'time_format: %I:%M%p %Z %m/%d/%y\n'):
            problems = check_config(self.write(GOOD.replace(line, '')))
            self.assertEqual(1, len(problems), line)
            self.assertIn('missing configuration value', problems[0])
            self.assertIn(line.split(':')[0], problems[0])

    def test_control_socket_path(self):
        self.assertEqual([], check_config(self.write(GOOD.replace('[server]', 'control_socket: @conf/b3.sock\n[server]'))))
        long = '/' + 'x' * 120 + '/b3.sock'
        self.assertIn('too long', check_config(self.write(GOOD.replace('[server]', 'control_socket: %s\n[server]' % long)))[0])
        self.assertIn('folder does not exist',
                      check_config(self.write(GOOD.replace('[server]', 'control_socket: /nonexistent/b3.sock\n[server]')))[0])

    def test_missing_game_log(self):
        problems = check_config(self.write(GOOD.replace('game_log: games.log\n', '')))
        self.assertEqual(['missing configuration value server::game_log (the et parser reads the game log)'], problems)

    def test_unknown_plugin(self):
        problems = check_config(self.write(GOOD + 'nosuchplugin:\n'))
        self.assertEqual(1, len(problems))
        self.assertTrue(problems[0].startswith('plugin nosuchplugin cannot be loaded'), problems)

    def test_missing_plugin_config(self):
        problems = check_config(self.write(GOOD.replace('@conf/plugin_welcome.ini', '@conf/gone.ini')))
        self.assertEqual(1, len(problems))
        self.assertIn('plugin welcome: configuration file not found', problems[0])

    def test_broken_plugin_config(self):
        self.write('<configuration><settings', 'broken.xml')
        problems = check_config(self.write(GOOD.replace('@conf/plugin_welcome.ini', '@conf/broken.xml')))
        self.assertEqual(1, len(problems))
        self.assertIn('plugin welcome: invalid configuration file', problems[0])

    def test_missing_admin(self):
        self.assertIn('missing admin plugin in plugins section',
                      check_config(self.write(GOOD.replace('admin: @b3/conf/plugin_admin.ini\n', ''))))


class Test_main(CheckConfigCase):

    def test_exit_codes(self):
        with self.assertRaises(SystemExit) as cm:
            main(self.write(GOOD))
        self.assertEqual(b3.exitcodes.OK, cm.exception.code)
        with self.assertRaises(SystemExit) as cm:
            main(self.write(GOOD.replace('parser: et', 'parser: nope')))
        self.assertEqual(b3.exitcodes.CONFIG, cm.exception.code)

    def test_command_line(self):
        # one "ERROR: <reason>" line per problem, nothing connects (no game server, no database here)
        bad = self.write(GOOD.replace('port: 27960', 'port: abc'))
        run = subprocess.run([sys.executable, os.path.join(ROOT, 'b3_run.py'), '--check-config', '-c', bad],
                             capture_output=True, text=True, timeout=60, cwd=ROOT)
        self.assertEqual(230, run.returncode, run.stderr)
        self.assertEqual(["ERROR: server::port must be a port number (found 'abc')"], run.stdout.splitlines())
        run = subprocess.run([sys.executable, os.path.join(ROOT, 'b3_run.py'), '--check-config', '-c', self.write(GOOD)],
                             capture_output=True, text=True, timeout=60, cwd=ROOT)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertTrue(run.stdout.startswith('OK: '), run.stdout)
