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

from unittest.mock import call
from unittest.mock import patch


class RconInjectionChecks(object):
    """
    Checks shared by the Source engine parsers (CS:GO, Insurgency): text coming from players (names, chat), config
    or RSS feeds is interpolated in rcon command lines, so it must not be able to end the current command (';',
    line breaks) or the current quoted argument ('"'). Tempbans under a minute must not become permanent bans.
    Mix into a TestCase whose setUp creates self.parser (with self.parser.output mocked) and self.player.
    """

    EVIL = 'hello"; rcon_password pwned; sm_rcon quit\nquit\r\x00exec evil.cfg'

    def written_commands(self, write_mock):
        return [c[0][0] for c in write_mock.call_args_list]

    def assert_safe(self, write_mock, expected_count=None):
        commands = self.written_commands(write_mock)
        self.assertTrue(commands)
        if expected_count is not None:
            self.assertEqual(expected_count, len(commands), commands)
        for cmd in commands:
            self.assertNotIn(';', cmd)
            self.assertNotIn('\n', cmd)
            self.assertNotIn('\r', cmd)
            self.assertNotIn('\x00', cmd)
            self.assertEqual(0, cmd.count('"') % 2, cmd)
        return commands

    def test_say(self):
        for sm_plugins in ({}, {"B3 Say": None}):
            self.parser.sm_plugins = sm_plugins
            with patch.object(self.parser.output, 'write') as write_mock:
                self.parser.say(self.EVIL)
            self.assert_safe(write_mock)

    def test_saybig(self):
        for sm_plugins in ({}, {"B3 Say": None}):
            self.parser.sm_plugins = sm_plugins
            with patch.object(self.parser.output, 'write') as write_mock:
                self.parser.saybig(self.EVIL)
            self.assert_safe(write_mock)

    def test_message(self):
        for sm_plugins in ({}, {"B3 Say": None}):
            self.parser.sm_plugins = sm_plugins
            with patch.object(self.parser.output, 'write') as write_mock:
                self.parser.message(self.player, self.EVIL)
            for cmd in self.assert_safe(write_mock):
                # the message stays one single quoted argument
                self.assertEqual(2, cmd.count('"'), cmd)
                self.assertTrue(cmd.endswith('"'), cmd)

    def test_kick_reason(self):
        with patch.object(self.parser.output, 'write') as write_mock:
            self.parser.do_kick(self.player, reason=self.EVIL)
        self.assertTrue(self.assert_safe(write_mock, 1)[0].startswith('sm_kick #2 hello'))

    def test_ban_reason(self):
        with patch.object(self.parser.output, 'write') as write_mock:
            self.parser.do_ban(self.player, reason=self.EVIL)
        commands = self.assert_safe(write_mock)
        self.assertTrue(commands[0].startswith('sm_addban 0 "STEAM_1:0:1111111" hello'), commands[0])

    def test_tempban_reason(self):
        with patch.object(self.parser.output, 'write') as write_mock:
            self.parser.do_tempban(self.player, duration='45m', reason=self.EVIL)
        commands = self.assert_safe(write_mock)
        self.assertTrue(commands[0].startswith('sm_addban 45 "STEAM_1:0:1111111" hello'), commands[0])

    def test_unban_by_ip(self):
        self.player.ip = '1.2.3.4;quit'
        with patch.object(self.parser.output, 'write') as write_mock:
            self.parser.do_unban_by_ip(self.player)
        self.assert_safe(write_mock, 1)

    def test_tempban_less_than_a_minute_is_not_permanent(self):
        # sm_addban 0 means a permanent ban
        for duration in ('30s', '1s', 0.5, 0, '0'):
            with patch.object(self.parser.output, 'write') as write_mock:
                self.parser.do_tempban(self.player, duration=duration, reason='test')
            commands = self.written_commands(write_mock)
            self.assertEqual('sm_addban 1 "STEAM_1:0:1111111" test', commands[0], duration)
            with patch.object(self.parser.output, 'write') as write_mock:
                self.parser.do_tempban(self.player, duration=duration)
            commands = self.written_commands(write_mock)
            self.assertEqual('sm_addban 1 "STEAM_1:0:1111111"', commands[0], duration)

    def test_tempban_through_parser_API(self):
        with patch.object(self.parser.output, 'write') as write_mock:
            self.parser.tempban(self.player, reason="test", duration="30s")
        self.assertIn(call('sm_addban 1 "STEAM_1:0:1111111" test'), write_mock.call_args_list)

    def test_getCvar_rejects_invalid_names(self):
        with patch.object(self.parser.output, 'write') as write_mock:
            self.assertIsNone(self.parser.getCvar('sv_cheats; quit'))
        self.assertFalse(write_mock.called)
