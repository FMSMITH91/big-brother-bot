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
import re
import unittest

from unittest.mock import Mock
from b3.clients import Clients
from b3.config import XmlConfigParser
from b3.parsers.iourt43 import Iourt43Parser
from tests import logging_disabled

# Iourt43Parser.__new__ patches Clients.newClient: restore it once this module is done
original_newClient = Clients.newClient
def tearDownModule():
    Clients.newClient = original_newClient


STATUS = """map: ut4_casa
num score ping name            lastmsg address               qport rate
--- ----- ---- --------------- ------- --------------------- ----- -----
  2     0   19 Joe^7                 0 145.99.135.227:27960  41893  8000
  4     0   48 Jack Daniels^7        0 83.175.191.27:64459   50308 20000
"""


class Iourt43TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from b3.parsers.q3a.abstractParser import AbstractParser
        from b3.fake import FakeConsole
        AbstractParser.__bases__ = (FakeConsole,)
        # Now parser inheritance hierarchy is :
        # Iourt43Parser -> Iourt42Parser -> Iourt41Parser -> AbstractParser -> FakeConsole -> Parser

    def setUp(self):
        self.parser_conf = XmlConfigParser()
        self.parser_conf.loadFromString("""<configuration>
                <settings name="server">
                    <set name="game_log"/>
                </settings>
            </configuration>""")
        with logging_disabled():
            self.console = Iourt43Parser(self.parser_conf)
        self.console.PunkBuster = None

    def tearDown(self):
        self.console.working = False


class Test_regPlayer(Iourt43TestCase):

    def match(self, line):
        m = re.match(self.console._regPlayer, line.strip())
        self.assertIsNotNone(m, line)
        return m.groupdict()

    def test_ip_has_no_port_nor_trailing_space(self):
        d = self.match('  2     0   19 Joe^7   0 145.99.135.227:27960  41893  8000')
        self.assertEqual('145.99.135.227', d['ip'])
        self.assertEqual('27960', d['port'])
        self.assertEqual('Joe^7', d['name'])
        self.assertEqual('41893', d['qport'])
        self.assertEqual('8000', d['rate'])

    def test_connecting_and_zombie(self):
        self.assertEqual('83.175.191.27', self.match('4     0 CNCT Dz!k^7   450 83.175.191.27:64459   50308 20000')['ip'])
        self.assertEqual('81.178.80.68', self.match('9     0 ZMBI ^7  1900 81.178.80.68:27960    10801  8000')['ip'])

    def test_loopback_and_bot(self):
        d = self.match('  0     0    0 Some Body^7   0 loopback  12345 25000')
        self.assertEqual('loopback', d['ip'])
        self.assertIsNone(d['port'])
        self.assertEqual('Some Body^7', d['name'])
        self.assertEqual('bot', self.match('  1     5    0 Boa^7   0 bot  0 25000')['ip'])


class Test_sync(Iourt43TestCase):

    def test_connected_players_are_kept_in_sync(self):
        # GIVEN
        self.console.write = Mock(return_value=STATUS)
        joe = Mock(cid='2', guid=None, ip='145.99.135.227')
        jack = Mock(cid='4', guid=None, ip='83.175.191.27')
        clients = {'2': joe, '4': jack}
        self.console.getByCidOrJoinPlayer = Mock(side_effect=lambda cid: clients.get(cid))
        # WHEN
        mlist = self.console.sync()
        # THEN
        self.assertDictEqual({'2': joe, '4': jack}, mlist)
        self.assertFalse(joe.disconnect.called)
        self.assertFalse(jack.disconnect.called)

    def test_player_with_other_ip_is_disconnected(self):
        # GIVEN
        self.console.write = Mock(return_value=STATUS)
        joe = Mock(cid='2', guid=None, ip='1.2.3.4')
        self.console.getByCidOrJoinPlayer = Mock(side_effect=lambda cid: joe if cid == '2' else None)
        # WHEN
        mlist = self.console.sync()
        # THEN
        self.assertDictEqual({}, mlist)
        self.assertTrue(joe.disconnect.called)
