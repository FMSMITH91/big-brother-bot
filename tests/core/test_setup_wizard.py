# -*- coding: utf-8 -*-

# ################################################################### #
#                                                                     #
#  BigBrotherBot(B3) (www.bigbrotherbot.net)                          #
#  Copyright (C) 2005 Michael "ThorN" Thornton                        #
#                                                                     #
#  This program is free software; you can redistribute it and/or      #
#  modify it under the terms of the GNU General Public License        #
#  as published by the Free Software Foundation; either version 2     #
#  of the License, or (at your option) any later version.             #
#                                                                     #
#  This program is distributed in the hope that it will be useful,    #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of     #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the       #
#  GNU General Public License for more details.                       #
#                                                                     #
#  You should have received a copy of the GNU General Public License  #
#  along with this program; if not, write to the Free Software        #
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA      #
#  02110-1301, USA.                                                   #
#                                                                     #
# ################################################################### #

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import b3
import b3.config
from b3 import setup_wizard
from b3.setup_wizard import Wizard, build_config, set_ini_value


def run_wizard(answers, path):
    """
    Run the wizard with scripted answers; returns (result, everything it printed).
    """
    replies = iter(answers)
    output = []

    def ask(prompt):
        output.append(prompt)
        try:
            return next(replies)
        except StopIteration:
            raise EOFError()

    wizard = Wizard(ask=ask, ask_secret=ask, say=lambda *a: output.append(' '.join(str(x) for x in a)))
    return wizard.run(path), '\n'.join(output)


class Test_set_ini_value(unittest.TestCase):

    def test_replaces_in_the_right_section_and_keeps_comments(self):
        text = "[b3]\n# the game\nparser: changeme\nport: 1\n\n[server]\n# port of the server\nport: 27960\n"
        text = set_ini_value(text, 'server', 'port', '28960')
        text = set_ini_value(text, 'b3', 'parser', 'cod')
        self.assertEqual("[b3]\n# the game\nparser: cod\nport: 1\n\n[server]\n# port of the server\nport: 28960\n",
                         text)

    def test_adds_missing_key_and_section_and_keeps_crlf(self):
        text = set_ini_value("[b3]\r\nparser: cod\r\n", 'b3', 'bot_name', 'bot')
        self.assertEqual("[b3]\r\nparser: cod\r\nbot_name: bot\r\n", text)
        self.assertIn('[server]\nrcon_password: x', set_ini_value("[b3]\nparser: cod\n", 'server', 'rcon_password', 'x'))


class Test_wizard(unittest.TestCase):

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        patcher = patch.object(b3, 'HOMEDIR', self.home)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.path = os.path.join(self.home, 'b3.ini')

    def load(self):
        config = b3.config.MainConfig(b3.config.load(self.path))
        self.assertEqual([], config.analyze())
        return config

    def test_call_of_duty_with_sqlite(self):
        # game 1 (cod), same computer, default IP and port, RCON password, game log, no PunkBuster,
        # SQLite in the default file, default bot name
        log = os.path.join(self.home, 'games_mp.log')
        result, output = run_wizard(['1', 'y', '', '', 'p@ss%word', log, 'n', '1', '', ''], self.path)
        self.assertEqual(self.path, result)
        config = self.load()
        self.assertEqual('cod', config.get('b3', 'parser'))
        self.assertEqual('sqlite://' + os.path.join(self.home, 'b3.db').replace('\\', '/'), config.get('b3', 'database'))
        self.assertEqual('b3', config.get('b3', 'bot_name'))
        self.assertEqual('auto', config.get('b3', 'time_zone'))
        self.assertEqual(('127.0.0.1', '28960', '127.0.0.1', 'p@ss%word', log, 'off'),
                         tuple(config.get('server', k) for k in ('public_ip', 'port', 'rcon_ip', 'rcon_password',
                                                                  'game_log', 'punkbuster')))
        # the sample's comments and other settings are kept
        with open(self.path) as f:
            text = f.read()
        self.assertIn('# The RCON pass of your gameserver', text)
        self.assertIn('[plugins]', text)
        # no PunkBuster: its plugin is not loaded
        self.assertIn('\n# punkbuster: @b3/conf/plugin_punkbuster.ini', text)
        self.assertNotIn('punkbuster', [p['name'] for p in config.get_plugins()])
        self.assertIn('does not exist yet', output)
        self.assertIn('!iamgod', output)

    def test_remote_server_rcon_game_with_mysql(self):
        # Battlefield 3 (no game log), other computer, MySQL
        bf3 = str([g[0] for g in setup_wizard.GAMES].index('bf3') + 1)
        answers = [bf3, 'n', '203.0.113.5', '', '', 'secret', 'y', '2', 'db.example.com', '', 'b3db', 'bot', 'dbp4ss',
                   'MyBot']
        result, _ = run_wizard(answers, self.path)
        self.assertEqual(self.path, result)
        config = self.load()
        self.assertEqual('bf3', config.get('b3', 'parser'))
        self.assertEqual('mysql://bot:dbp4ss@db.example.com:3306/b3db', config.get('b3', 'database'))
        self.assertEqual(('203.0.113.5', '47200', '203.0.113.5', 'on'),
                         tuple(config.get('server', k) for k in ('public_ip', 'port', 'rcon_ip', 'punkbuster')))
        self.assertEqual('MyBot', config.get('b3', 'bot_name'))
        self.assertIn('punkbuster', [p['name'] for p in config.get_plugins()])

    def test_invalid_answers_are_asked_again(self):
        answers = ['999', 'cod', 'maybe', 'y', 'not an ip!', '', '70000', '', 'pw', 'games_mp.log', 'n',
                   '3', '', 'abc', '', 'b3', 'b3', 'pa@ss', '', '', 'b3', 'b3', 'ok', '']
        result, output = run_wizard(answers, self.path)
        self.assertEqual(self.path, result)
        for message in ('type a number from the list', 'answer y or n', 'type an IP address',
                        'type a port number', 'cannot contain @'):
            self.assertIn(message, output)
        self.assertEqual('postgresql://b3:ok@localhost:5432/b3', self.load().get('b3', 'database'))

    def test_existing_file_kept_unless_confirmed(self):
        with open(self.path, 'w') as f:
            f.write('[b3]\nparser: changeme\n')
        result, output = run_wizard(['n'], self.path)
        self.assertIsNone(result)
        self.assertIn('Nothing changed', output)
        result, _ = run_wizard(['y', '1', 'y', '', '', 'pw', 'games_mp.log', 'n', '1', '', ''], self.path)
        self.assertEqual(self.path, result)
        with open(self.path + '.bak') as f:
            self.assertEqual('[b3]\nparser: changeme\n', f.read())

    def test_stopping_writes_nothing(self):
        result, output = run_wizard(['1', 'y'], self.path)  # then end of input
        self.assertIsNone(result)
        self.assertIn('nothing changed', output)
        self.assertFalse(os.path.exists(self.path))

    def test_every_listed_game_has_a_parser(self):
        for game in setup_wizard.GAMES:
            text = build_config('[b3]\nparser: x\ndatabase: x\nbot_name: b3\n[plugins]\nadmin: @b3/conf/plugin_admin.ini\n',
                                {'parser': game[0], 'database': 'sqlite://:memory:', 'public_ip': '1.2.3.4',
                                 'port': 1, 'rcon_ip': '1.2.3.4', 'rcon_password': 'x'})
            self.assertEqual([], setup_wizard.validate(text), game[0])


if __name__ == '__main__':
    unittest.main()
