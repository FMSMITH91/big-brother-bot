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

from unittest.mock import Mock
from b3.config import XmlConfigParser
from b3.parsers.smg11 import Smg11Parser


class Smg11TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from b3.parsers.q3a.abstractParser import AbstractParser
        from b3.fake import FakeConsole
        AbstractParser.__bases__ = (FakeConsole,)
        # Now parser inheritance hierarchy is :
        # Smg11Parser -> AbstractParser -> FakeConsole -> Parser
        logging.getLogger('output').setLevel(logging.ERROR)

    def setUp(self):
        self.parser_conf = XmlConfigParser()
        self.parser_conf.loadFromString("""<configuration>
                <settings name="server">
                    <set name="game_log"/>
                </settings>
            </configuration>""")
        self.console = Smg11Parser(self.parser_conf)
        self.console.write = Mock(return_value='')
        self.console.PunkBuster = None

    def tearDown(self):
        self.console.working = False


class Test_parseUserInfo(Smg11TestCase):

    def test_userinfo_without_leading_backslash(self):
        data = self.console.parseUserInfo('2 n\\Ghost\\t\\0\\model\\wq_male2/red\\cl_guid\\0123456789ABCDEF')
        self.assertEqual('Ghost', data['name'])
        self.assertEqual('wq_male2/red', data['model'])
        self.assertEqual('0123456789ABCDEF', data['guid'])
        self.assertNotIn('Ghost', data)

    def test_new_client_is_created(self):
        self.console.OnClientuserinfochanged('clientuserinfochanged',
                                             '2 n\\Ghost\\t\\0\\ip\\11.22.33.44\\cl_guid\\0123456789ABCDEF')
        client = self.console.clients.getByCID('2')
        self.assertIsNotNone(client)
        self.assertEqual('Ghost', client.name)


class Test_connecting_slots(Smg11TestCase):

    def test_slot_released_when_dumpuser_fails(self):
        self.console.queryClientUserInfoByCid = Mock(return_value=None)
        self.console.OnClientuserinfochanged('clientuserinfochanged', '3 \\n\\Joe\\t\\1\\cl_guid\\0123456789ABCDEF')
        self.assertNotIn('3', self.console._connectingSlots)

    def test_slots_are_per_instance(self):
        other = Smg11Parser(self.parser_conf)
        self.console._connectingSlots.append('5')
        self.assertNotIn('5', other._connectingSlots)


class Test_sync(Smg11TestCase):

    def test_sync(self):
        # GIVEN
        self.console.getPlayerList = Mock(return_value={
            '2': {'slot': '2', 'guid': 'abc', 'ip': '1.1.1.1'},
            '3': {'slot': '3', 'ip': '2.2.2.2'},
            '4': {'slot': '4', 'guid': 'zzz', 'ip': '3.3.3.3'},
        })
        joe = Mock(cid='2', guid='abc', ip='1.1.1.1')
        jack = Mock(cid='3', guid=None, ip='2.2.2.2')
        averell = Mock(cid='4', guid='xxx', ip='3.3.3.3')
        clients = {'2': joe, '3': jack, '4': averell}
        self.console.getByCidOrJoinPlayer = Mock(side_effect=lambda cid: clients.get(cid))
        # WHEN
        mlist = self.console.sync()
        # THEN
        self.assertDictEqual({'2': joe, '3': jack}, mlist)
        self.assertTrue(averell.disconnect.called)
