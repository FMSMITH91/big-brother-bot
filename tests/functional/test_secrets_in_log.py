# -*- coding: utf-8 -*-
"""
The database password never reaches b3.log, the console or health.json (linuxgsm-panel request 8), even at the most
verbose log level and when the connection fails. The RCON password is checked by test_urt_smoke.py.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PASSWORD = 'Db-4f81c-Pw'
RCON_PASSWORD = 'Rc0n-91b2e-Pw'


class Test_secrets_in_log(unittest.TestCase):

    def test_database_password_on_failed_connection(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        open(os.path.join(d, 'games.log'), 'w').close()
        config = os.path.join(d, 'b3.ini')
        with open(config, 'w') as f:
            f.write("""[b3]
parser: et
database: mysql://b3:%(db)s@127.0.0.1:1/b3
bot_name: b3
bot_prefix: b3:
time_format: %%H:%%M
log_level: 1
logfile: %(d)s/b3.log
[server]
rcon_password: %(rcon)s
port: 27999
game_log: %(d)s/games.log
public_ip: 127.0.0.1
[update]
channel: skip
[plugins]
admin: @b3/conf/plugin_admin.ini
""" % {'db': DB_PASSWORD, 'rcon': RCON_PASSWORD, 'd': d})
        run = subprocess.run([sys.executable, '-W', 'ignore', os.path.join(ROOT, 'b3_run.py'), '-c', config],
                             cwd=ROOT, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
                             env=dict(os.environ, HOME=d))
        self.assertEqual(233, run.returncode, run.stdout + run.stderr)  # b3.exitcodes.DATABASE
        with open(os.path.join(d, 'b3.log'), encoding='utf-8', errors='replace') as f:
            log = f.read()
        self.assertIn('Connecting to MySQL database', log)
        health = open(os.path.join(d, 'health.json')).read()
        self.assertEqual(233, json.loads(health)['exit_code'])
        for where, text in (('b3.log', log), ('stdout', run.stdout), ('stderr', run.stderr), ('health.json', health)):
            self.assertNotIn(DB_PASSWORD, text, where)
            self.assertNotIn(RCON_PASSWORD, text, where)


if __name__ == '__main__':
    unittest.main()
