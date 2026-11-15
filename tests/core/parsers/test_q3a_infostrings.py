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
from b3.parsers.smg import SmgParser
from b3.parsers.wop import WopParser


class InfostringTestCase(unittest.TestCase):

    parser_class = None

    @classmethod
    def setUpClass(cls):
        from b3.parsers.q3a.abstractParser import AbstractParser
        from b3.fake import FakeConsole
        AbstractParser.__bases__ = (FakeConsole,)
        logging.getLogger('output').setLevel(logging.ERROR)

    def setUp(self):
        self.parser_conf = XmlConfigParser()
        self.parser_conf.loadFromString("""<configuration>
                <settings name="server">
                    <set name="game_log"/>
                </settings>
            </configuration>""")
        self.console = self.parser_class(self.parser_conf)
        self.console.write = Mock(return_value='')
        self.console.PunkBuster = None

    def tearDown(self):
        self.console.working = False


class Test_smg_parseUserInfo(InfostringTestCase):

    parser_class = SmgParser

    def test_userinfo_without_leading_backslash(self):
        data = self.console.parseUserInfo('2 n\\Ghost\\t\\0\\model\\wq_male2/red\\ip\\11.22.33.44:27960')
        self.assertEqual('Ghost', data['name'])
        self.assertEqual('wq_male2/red', data['model'])
        self.assertEqual('11.22.33.44', data['ip'])
        self.assertNotIn('Ghost', data)


class Test_wop_parseUserInfo(InfostringTestCase):

    parser_class = WopParser

    def test_userinfo_without_leading_backslash(self):
        data = self.console.parseUserInfo('3 n\\Dr.Schraube\\t\\0\\model\\padman/padsoldier_red')
        self.assertEqual('Dr.Schraube', data['name'])
        self.assertEqual('padman/padsoldier_red', data['model'])
        self.assertNotIn('Dr.Schraube', data)

    def test_new_client_from_userinfo_without_leading_backslash(self):
        # GIVEN a ClientConnect line was seen for that slot
        self.console._clientConnectID = '3'
        self.console._clientConnectGuid = '0123456789ABCDEF'
        self.console._clientConnectIp = '11.22.33.44'
        # WHEN
        self.console.OnClientuserinfochanged('clientuserinfochanged', '3 n\\Dr.Schraube\\t\\0\\model\\padman/padsoldier_red')
        # THEN
        client = self.console.clients.getByCID('3')
        self.assertIsNotNone(client)
        self.assertEqual('Dr.Schraube', client.name)
