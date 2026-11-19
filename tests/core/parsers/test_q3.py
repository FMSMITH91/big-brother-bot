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

import logging
import unittest

from unittest.mock import Mock, patch
from b3.config import XmlConfigParser
from b3.parsers.q3 import Q3Parser
from tests.core.parsers.q3_engine_helpers import dumpuser_reply, fake_rcon


class Q3TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from b3.parsers.q3a.abstractParser import AbstractParser
        from b3.fake import FakeConsole
        AbstractParser.__bases__ = (FakeConsole,)
        # Now parser inheritance hierarchy is :
        # Q3Parser -> AbstractParser -> FakeConsole -> Parser
        logging.getLogger('output').setLevel(logging.ERROR)

    def setUp(self):
        self.parser_conf = XmlConfigParser()
        self.parser_conf.loadFromString("""<configuration>
                <settings name="server">
                    <set name="game_log"/>
                </settings>
            </configuration>""")
        self.console = Q3Parser(self.parser_conf)
        self.console.write = Mock(return_value='')
        self.console.PunkBuster = None

    def tearDown(self):
        self.console.working = False

    def queued_events(self, line):
        with patch.object(self.console, 'queueEvent') as queueEvent:
            self.console.parseLine(line)
        return [c[0][0].type for c in queueEvent.call_args_list]


class Test_connecting_slots(Q3TestCase):

    def test_slot_released_when_dumpuser_fails(self):
        # GIVEN dumpuser does not return the userinfo (player left, rcon timeout, ...)
        self.console.queryClientUserInfoByCid = Mock(return_value=None)
        # WHEN a userinfo without ip is received
        self.console.OnClientuserinfochanged('clientuserinfochanged', '3 n\\Joe\\t\\1\\cl_guid\\0123456789ABCDEF')
        # THEN the slot is not left locked
        self.assertNotIn('3', self.console._connectingSlots)
        # and the next userinfo for that slot is processed
        self.console.queryClientUserInfoByCid = Mock(return_value='3 \\ip\\11.22.33.44')
        self.console.OnClientuserinfochanged('clientuserinfochanged', '3 n\\Joe\\t\\1\\cl_guid\\0123456789ABCDEF')
        self.assertIsNotNone(self.console.clients.getByCID('3'))

    def test_slots_are_per_instance(self):
        other = Q3Parser(self.parser_conf)
        self.console._connectingSlots.append('5')
        self.assertNotIn('5', other._connectingSlots)


class Test_OnClientconnect(Q3TestCase):

    def test_client_connect_line(self):
        # GIVEN
        self.console.queryClientUserInfoByCid = Mock(
            return_value='3 \\name\\Joe\\ip\\11.22.33.44\\cl_guid\\0123456789ABCDEF')
        # WHEN
        with patch.object(self.console, 'queueEvent') as queueEvent:
            self.console.parseLine('0:00 ClientConnect: 3')
        # THEN
        events = [c[0][0] for c in queueEvent.call_args_list]
        join = [e for e in events if e.type == self.console.getEventID('EVT_CLIENT_JOIN')]
        self.assertEqual(1, len(join))
        self.assertIsNotNone(join[0].client)
        self.assertEqual('3', join[0].client.cid)
        self.assertEqual('11.22.33.44', join[0].client.ip)


class Test_OnKill(Q3TestCase):

    def setUp(self):
        Q3TestCase.setUp(self)
        self.console.queryClientUserInfoByCid = Mock(return_value=None)
        self.joe = self.console.clients.newClient('3', name='Joe', guid='0123456789ABCDEF', ip='11.22.33.44')

    def test_falling_is_a_suicide(self):
        self.assertIn(self.console.getEventID('EVT_CLIENT_SUICIDE'), self.queued_events('1:00 Kill: 1022 3 19: <world> killed Joe by MOD_FALLING'))

    def test_lava_is_a_suicide(self):
        self.assertIn(self.console.getEventID('EVT_CLIENT_SUICIDE'), self.queued_events('1:00 Kill: 1022 3 16: <world> killed Joe by MOD_LAVA'))


# rcon status of Quake 3 1.32c (id's sv_ccmds.c SV_Status_f): the address is "ip:port", "bot" for a bot, and the
# ping is CNCT while a player connects
STATUS_Q3 = '''\
map: q3dm17
num score ping name            lastmsg address               qport rate
--- ----- ---- --------------- ------- --------------------- ----- -----
  0     5   48 Courgette^7           0 81.56.143.41:27960    12345 25000
  1     0 CNCT Newbie^7              0 81.56.143.42:27960    23456 25000
  2     3    0 Sarge^7               0 bot                       0 16384
'''


class Test_status(Q3TestCase):
    """
    linuxgsm-panel research (2026-11-18): the q3 status regex wanted a bare ip, but status prints "ip:port", so no row
    matched: getPlayerPings returned nothing and sync never confirmed a player.
    """

    def setUp(self):
        Q3TestCase.setUp(self)
        self.console.write = Mock(side_effect=lambda cmd, *a, **k: STATUS_Q3 if cmd == 'status' else '')

    def test_player_list(self):
        players = self.console.getPlayerList()
        self.assertEqual('81.56.143.41', players['0']['ip'])
        self.assertEqual('27960', players['0']['port'])
        self.assertEqual('Courgette^7', players['0']['name'])
        self.assertEqual('CNCT', players['1']['ping'])
        self.assertIn('2', players)

    def test_pings_skip_connecting_players(self):
        self.assertEqual({'0': 48, '2': 0}, self.console.getPlayerPings())


class Test_dumpuser(Q3TestCase):
    """
    linuxgsm-panel round D (F-D1): Quake 3 1.32, ET 2.60b and ET: Legacy look dumpuser up by name only, so
    "dumpuser <slot>" never found a human player and no human was authorized.
    """

    COURGETTE = {'ip': '81.56.143.41:27960', 'name': 'Courgette', 'cl_guid': '201AB4BBC40B4EC7445B49CE82D209EC'}
    NEWBIE = {'ip': '81.56.143.42:27960', 'name': 'Newbie', 'cl_guid': 'AAAABBBBCCCCDDDDEEEEFFFF00001111'}

    def use(self, status=STATUS_Q3, players=(COURGETTE, NEWBIE), width=20):
        self.sent = []
        self.console.write = Mock(side_effect=fake_rcon(status, list(players), width, self.sent))

    def test_quake3_and_etlegacy_key_widths(self):
        for width in (20, 26):
            self.use(width=width)
            info = self.console.parseUserInfo(self.console.queryClientUserInfoByCid('0'))
            self.assertEqual('201AB4BBC40B4EC7445B49CE82D209EC', info['cl_guid'], width)
            self.assertEqual('Courgette', info['name'], width)
            self.assertEqual('0', info['cid'])

    def test_asks_by_name_not_slot(self):
        self.use()
        self.console.queryClientUserInfoByCid('0')
        self.assertIn('dumpuser "Courgette"', self.sent)
        self.assertNotIn('dumpuser 0', self.sent)

    def test_connecting_player(self):
        self.use()
        info = self.console.parseUserInfo(self.console.queryClientUserInfoByCid('1'))
        self.assertEqual('AAAABBBBCCCCDDDDEEEEFFFF00001111', info['cl_guid'])

    def test_slot_not_in_status(self):
        self.use()
        self.assertIsNone(self.console.queryClientUserInfoByCid('7'))
        self.assertEqual([], [c for c in self.sent if c.startswith('dumpuser')])

    def test_copied_name_never_gets_the_other_guid(self):
        # slot 1 takes Courgette's name: the engine would answer with the first match, slot 0
        status = STATUS_Q3.replace('Newbie^7   ', '^1Courgette^7')
        self.use(status=status, players=(self.COURGETTE, dict(self.NEWBIE, name='^1Courgette')))
        self.assertIsNone(self.console.queryClientUserInfoByCid('1'))
        self.assertNotIn('dumpuser "Courgette"', self.sent)

    def test_reply_for_another_name_is_ignored(self):
        self.use()
        self.console.write = Mock(side_effect=lambda cmd, *a, **k: STATUS_Q3 if cmd == 'status' else
                                  dumpuser_reply(dict(self.COURGETTE, name='Courgette2')))
        self.assertIsNone(self.console.queryClientUserInfoByCid('0'))

    def test_reply_from_another_ip_is_ignored(self):
        self.use(players=(dict(self.COURGETTE, ip='10.9.9.9:27960'),))
        self.assertIsNone(self.console.queryClientUserInfoByCid('0'))

    def test_unsafe_name_is_never_sent(self):
        for name in ('Joe;quit', 'Joe"x', 'a\\b', 'x//y', 'x/*y'):
            status = STATUS_Q3.replace('Courgette^7', (name + '^7').ljust(11))
            self.use(status=status, players=(dict(self.COURGETTE, name=name),))
            self.console.queryClientUserInfoByCid('0')
            self.assertEqual(['dumpuser 0'], [c for c in self.sent if c.startswith('dumpuser')], name)

    def test_clean_name_like_q_cleanstr(self):
        self.assertEqual('Big ^oe', self.console.cleanName('^1Big ^^Joe^7'))
        self.assertEqual('ab', self.console.cleanName('a\x01\xe9b'))

    def test_client_connect_creates_and_authorizes(self):
        self.use()
        self.console.parseLine('0:01 ClientConnect: 0')
        client = self.console.clients.getByCID('0')
        self.assertIsNotNone(client)
        self.assertEqual('81.56.143.41', client.ip)
        self.assertEqual('201AB4BBC40B4EC7445B49CE82D209EC', client.guid)
        self.assertTrue(client.authed)
