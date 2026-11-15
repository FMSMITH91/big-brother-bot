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
from b3.parsers.oa081 import Oa081Parser


class Oa081TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from b3.parsers.q3a.abstractParser import AbstractParser
        from b3.fake import FakeConsole
        AbstractParser.__bases__ = (FakeConsole,)
        # Now parser inheritance hierarchy is :
        # Oa081Parser -> AbstractParser -> FakeConsole -> Parser
        logging.getLogger('output').setLevel(logging.ERROR)

    def setUp(self):
        self.parser_conf = XmlConfigParser()
        self.parser_conf.loadFromString("""<configuration>
                <settings name="server">
                    <set name="game_log"/>
                </settings>
            </configuration>""")
        self.console = Oa081Parser(self.parser_conf)
        self.console.write = Mock(return_value='')
        self.console.PunkBuster = None

    def tearDown(self):
        self.console.working = False

    def queued_events(self, line):
        with patch.object(self.console, 'queueEvent') as queueEvent:
            self.console.parseLine(line)
        return [c[0][0].type for c in queueEvent.call_args_list]


class Test_connecting_slots(Oa081TestCase):

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

    def test_no_endless_retry_when_dumpuser_has_no_guid(self):
        # GIVEN dumpuser does not give a guid either
        self.console.queryClientUserInfoByCid = Mock(return_value='3 \\name\\Joe\\ip\\11.22.33.44')
        # WHEN
        self.console.OnClientuserinfochanged('clientuserinfochanged', '3 n\\Joe\\t\\1')
        # THEN dumpuser was retried once only, and the slot is released
        self.assertEqual(1, self.console.queryClientUserInfoByCid.call_count)
        self.assertNotIn('3', self.console._connectingSlots)

    def test_slots_are_per_instance(self):
        other = Oa081Parser(self.parser_conf)
        self.console._connectingSlots.append('5')
        self.assertNotIn('5', other._connectingSlots)


class Test_OnKill(Oa081TestCase):

    def setUp(self):
        Oa081TestCase.setUp(self)
        self.console.queryClientUserInfoByCid = Mock(return_value=None)
        self.joe = self.console.clients.newClient('3', name='Joe', guid='0123456789ABCDEF', ip='11.22.33.44')

    def test_falling_is_a_suicide(self):
        self.assertIn(self.console.getEventID('EVT_CLIENT_SUICIDE'), self.queued_events('1:00 Kill: 1022 3 19: <world> killed Joe by MOD_FALLING'))

    def test_lava_is_a_suicide(self):
        self.assertIn(self.console.getEventID('EVT_CLIENT_SUICIDE'), self.queued_events('1:00 Kill: 1022 3 16: <world> killed Joe by MOD_LAVA'))
