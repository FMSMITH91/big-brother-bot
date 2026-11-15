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
import io
from unittest.mock import call, patch, Mock

from mockito import mock, verify
import unittest

from b3.clients import Client
from b3.config import XmlConfigParser
from b3.parsers.et import EtParser


log = logging.getLogger("test")
log.setLevel(logging.INFO)


class EtTestCase(unittest.TestCase):
    """
    Test case that is suitable for testing et parser specific features
    """

    @classmethod
    def setUpClass(cls):
        from b3.parsers.q3a.abstractParser import AbstractParser
        from b3.fake import FakeConsole

        AbstractParser.__bases__ = (FakeConsole,)
        # Now parser inheritance hierarchy is :
        # EtParser -> AbstractParser -> FakeConsole -> Parser

        logging.getLogger('output').setLevel(logging.ERROR)

    def setUp(self):
        self.parser_conf = XmlConfigParser()
        self.parser_conf.loadFromString("""<configuration>
                <settings name="server">
                    <set name="game_log"/>
                </settings>
            </configuration>""")
        self.console = EtParser(self.parser_conf)
        self.console.write = Mock()
        self.console.PunkBuster = None  # no Punkbuster support in that game

    def tearDown(self):
        if hasattr(self, "parser"):
            del self.parser.clients
            self.parser.working = False


class Test_parser_API_implementation(EtTestCase):
    """Test case that is responsible for testing all methods of the b3.parser.Parser class API that
    have to override because they have to talk to their targeted game server in their specific way"""

    def test_say(self):
        # GIVEN
        self.console.msgPrefix = "B3:"
        # WHEN
        self.console.say("something")
        # GIVEN
        self.console.msgPrefix = None
        # WHEN
        self.console.say("something else")
        # THEN
        self.assertListEqual(self.console.write.mock_calls, [call('qsay B3: something'),
                                                             call('qsay something else')])

    def test_saybig(self):
        # GIVEN
        self.console.msgPrefix = "B3:"
        # WHEN
        self.console.saybig("something")
        # GIVEN
        self.console.msgPrefix = None
        # WHEN
        self.console.saybig("something else")
        # THEN
        self.assertListEqual(self.console.write.mock_calls, [call('qsay B3: ^1something'),
                                                             call('qsay B3: ^2something'),
                                                             call('qsay B3: ^3something'),
                                                             call('qsay B3: ^4something'),
                                                             call('qsay B3: ^5something'),
                                                             call('qsay ^1something else'),
                                                             call('qsay ^2something else'),
                                                             call('qsay ^3something else'),
                                                             call('qsay ^4something else'),
                                                             call('qsay ^5something else')])

    def test_message(self):
        superman = Client(console=self.console, cid="11")
        # GIVEN
        self.console.msgPrefix = "B3:"
        self.console.pmPrefix = "^3[pm]^7"
        # WHEN
        self.console.message(superman, "something")
        # GIVEN
        self.console.msgPrefix = None
        self.console.pmPrefix = None
        # WHEN
        self.console.message(superman, "something else")
        # THEN
        self.assertListEqual(self.console.write.mock_calls, [call('qsay B3: ^3[pm]^7 something'),
                                                             call('qsay something else')])

class Test_startup_and_clients(EtTestCase):

    CONNECTINFO = '1579:03ConnectInfo: 3: E24F9B2702B9E4A1223E905BF597FA92: ^w[^2AS^w]^2Lead: 3: 3: 24.153.180.106:2794'

    def test_startup(self):
        self.console.startup()
        world = self.console.clients.getByCID('-1')
        self.assertIsNotNone(world)
        self.assertEqual('et:WORLD', world.guid)
        self.assertIsNotNone(self.console.PunkBuster)

    def test_connectinfo_creates_client(self):
        self.console.parseLine(self.CONNECTINFO)
        client = self.console.clients.getByCID('3')
        self.assertIsNotNone(client)
        self.assertEqual('et:E24F9B2702B9E4A1223E905BF597FA92', client.guid)
        self.assertEqual('24.153.180.106', client.ip)
        self.assertEqual('[AS]Lead', client.name)

    def test_connectinfo_again_keeps_same_client(self):
        self.console.parseLine(self.CONNECTINFO)
        client = self.console.clients.getByCID('3')
        with patch.object(self.console, 'queueEvent') as queueEvent:
            self.console.parseLine(self.CONNECTINFO.replace('^2Lead', '^2Leader'))
        self.assertIs(client, self.console.clients.getByCID('3'))
        self.assertEqual('[AS]Leader', client.name)
        join = [c[0][0] for c in queueEvent.call_args_list
                if c[0][0].type == self.console.getEventID('EVT_CLIENT_JOIN')]
        self.assertEqual(1, len(join))
        self.assertIs(client, join[0].client)

    def test_userinfo_changed_guid_updates_client(self):
        self.console.parseLine(self.CONNECTINFO)
        self.console.parseLine('1579:04ClientUserinfoChangedGUID: 3 E24F9B2702B9E4A1223E905BF597FA92 n\\^1Joe\\t\\2\\c\\1')
        client = self.console.clients.getByCID('3')
        self.assertEqual('Joe', client.name)
