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
        self.assertListEqual(self.console.write.mock_calls, [call('say B3: something'),
                                                             call('say something else')])

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
        self.assertListEqual(self.console.write.mock_calls, [call('say B3: ^1something'),
                                                             call('say B3: ^2something'),
                                                             call('say B3: ^3something'),
                                                             call('say B3: ^4something'),
                                                             call('say B3: ^5something'),
                                                             call('say ^1something else'),
                                                             call('say ^2something else'),
                                                             call('say ^3something else'),
                                                             call('say ^4something else'),
                                                             call('say ^5something else')])

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
        self.assertListEqual(self.console.write.mock_calls, [call('say B3: ^3[pm]^7 something'),
                                                             call('say something else')])

class Test_startup_and_clients(EtTestCase):

    CONNECTINFO = '1579:03ConnectInfo: 3: E24F9B2702B9E4A1223E905BF597FA92: ^w[^2AS^w]^2Lead: 3: 3: 24.153.180.106:2794'

    def test_startup(self):
        from b3.cvar import Cvar
        with patch.object(self.console, 'getCvar', return_value=Cvar('sv_punkbuster', value='1')):
            self.console.startup()
        world = self.console.clients.getByCID('-1')
        self.assertIsNotNone(world)
        self.assertEqual('et:WORLD', world.guid)
        self.assertIsNotNone(self.console.PunkBuster)

    def test_startup_without_punkbuster(self):
        # vanilla ET 2.60b as LinuxGSM installs it: PunkBuster's empty player list made every sync drop all players
        from b3.cvar import Cvar
        for value in (Cvar('sv_punkbuster', value='0'), None):
            with patch.object(self.console, 'getCvar', return_value=value):
                self.console.startup()
            self.assertIsNone(self.console.PunkBuster)

    def test_connectinfo_creates_client(self):
        self.console.parseLine(self.CONNECTINFO)
        client = self.console.clients.getByCID('3')
        self.assertIsNotNone(client)
        self.assertEqual('et:E24F9B2702B9E4A1223E905BF597FA92', client.guid)
        self.assertEqual('E24F9B2702B9E4A1223E905BF597FA92', client.pbid)
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


# rcon status of vanilla ET 2.60b (no guid column), from the round 3 live test on 2026-11-18
STATUS_ET260 = """\
map: oasis
num score ping name            lastmsg address               qport rate
--- ----- ---- --------------- ------- --------------------- ----- -----
  5     0   48 B3Tester^7            0 192.0.2.15:27970       1773 25000
"""


class Test_vanilla_et260b(EtTestCase):
    """
    Round 3 live test (2026-11-18), vanilla ET 2.60b (LinuxGSM wetserver): every userinfo line raised
    "Could not parse line 'cid'", so no player was ever created; a say from the unknown player crashed the admin plugin
    (client None), and "ClientDisconnect: 7" raised "no such group". These are the lines the server wrote.
    """

    LINES = [
        '1100:00 ClientConnect: 5',
        '1100:03 ClientUserinfoChanged: 5 n\\B3Tester\\t\\1\\c\\0\\r\\0\\m\\0000000\\s\\0000000\\dn\\\\dr\\0'
        '\\w\\0\\lw\\0\\sw\\0\\mu\\0\\ref\\0',
        '1100:06 ClientBegin: 5',
        '1100:09 Userinfo: \\g_password\\none\\cl_guid\\B3B3B3B3B3B3B3B3B3B3B3B3B3000001\\cl_wwwDownload\\1'
        '\\name\\B3Tester\\rate\\25000\\snaps\\20\\cl_anonymous\\0\\cl_punkbuster\\0\\ip\\192.0.2.15:27970',
    ]

    def setUp(self):
        EtTestCase.setUp(self)
        self.console.write = Mock(side_effect=lambda cmd, *args, **kwargs: STATUS_ET260 if cmd == 'status' else '')
        self.queued = []
        self.console.queueEvent = lambda event, expire=10: self.queued.append(event)

    def events(self, key):
        return [e for e in self.queued if e.type == self.console.getEventID(key)]

    def test_player_is_created_and_authenticated(self):
        with patch.object(self.console, 'error') as error:
            for line in self.LINES:
                self.console.parseLine(line)
        error.assert_not_called()
        client = self.console.clients.getByCID('5')
        self.assertIsNotNone(client)
        self.assertEqual('B3Tester', client.name)
        self.assertEqual('et:B3B3B3B3B3B3B3B3B3B3B3B3B3000001', client.guid)
        self.assertEqual('192.0.2.15', client.ip)
        self.assertTrue(client.authed)
        # round 3b: pbid was 'et:' + cl_guid, 35 characters for the VARCHAR(32) clients.pbid column ("Data too long")
        self.assertEqual('B3B3B3B3B3B3B3B3B3B3B3B3B3000001', client.pbid)
        self.assertLessEqual(len(client.pbid), 32)
        self.assertLessEqual(len(client.guid), 36)

    def test_say_from_known_player(self):
        for line in self.LINES:
            self.console.parseLine(line)
        self.console.parseLine('1100:12 say: B3Tester: !help')
        says = self.events('EVT_CLIENT_SAY')
        self.assertEqual(['!help'], [e.data for e in says])
        self.assertIs(self.console.clients.getByCID('5'), says[0].client)

    def test_say_from_unknown_player_makes_no_event(self):
        self.console.parseLine('1100:12 say: Nobody: !help')
        self.assertEqual([], self.events('EVT_CLIENT_SAY'))

    def test_disconnect(self):
        for line in self.LINES:
            self.console.parseLine(line)
        with patch.object(self.console, 'error') as error:
            self.console.parseLine('1101:24 ClientDisconnect: 5')
        error.assert_not_called()
        self.assertIsNone(self.console.clients.getByCID('5'))

    def test_userinfo_without_a_valid_guid(self):
        self.console.parseLine('1100:00 ClientConnect: 6')
        self.console.parseLine('1100:03 ClientUserinfoChanged: 6 n\\Other\\t\\1')
        client = self.console.clients.getByCID('6')
        self.assertIsNotNone(client)
        self.assertEqual('', client.guid)

    def test_status_without_guid_column(self):
        players = self.console.getPlayerList()
        self.assertEqual('B3Tester^7', players['5']['name'])
        self.assertEqual('192.0.2.15', players['5']['ip'])
        self.assertNotIn('guid', players['5'])


class Test_status_preamble(EtTestCase):

    def test_header_found_after_other_lines(self):
        status = 'hostname: x\nversion : ET 2.60b\nos: linux\nmap: oasis\n\n' + STATUS_ET260.split('\n', 1)[1]
        self.assertIs(self.console._regPlayerNoGuid, self.console.getStatusRegex(status))
