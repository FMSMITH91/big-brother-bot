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
