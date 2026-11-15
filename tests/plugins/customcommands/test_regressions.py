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

from textwrap import dedent
from mockito import when
from b3.config import CfgConfigParser
from b3.plugins.customcommands import CustomcommandsPlugin
from tests import logging_disabled
from tests.plugins.customcommands import CustomcommandsTestCase

with logging_disabled():
    from b3.fake import FakeClient


class Test_replacement_is_literal(CustomcommandsTestCase):
    """
    Player input and player names must be used literally (no regex backslash escapes processing).
    """

    def setUp(self):
        CustomcommandsTestCase.setUp(self)
        self.conf = CfgConfigParser()
        self.p = CustomcommandsPlugin(self.console, self.conf)
        self.p.onLoadConfig()
        self.p.onStartup()
        self.player1 = FakeClient(console=self.console, name="Player1", guid="player1GUID", pbid="player1PBID")
        self.player2 = FakeClient(console=self.console, name="Pl\\ayer\\1", guid="player2GUID", pbid="player2PBID")
        self.player1.connects(cid="slot1")
        self.player2.connects(cid="slot2")

    def render(self, template, data=""):
        return self.p._render_cmd_template(template, data=data, client=self.player1)

    def test_ARG_OPT_backslashes(self):
        self.assertEqual("say C:\\dir", self.render("say <ARG:OPT:f00>", data="C:\\dir"))
        self.assertEqual("say a\\1b", self.render("say <ARG:OPT:f00>", data="a\\1b"))
        self.assertEqual("say a\\gb", self.render("say <ARG:OPT:f00>", data="a\\gb"))

    def test_ARG_FIND_PLAYER_name_with_backslashes(self):
        when(self.p._adminPlugin).findClientPrompt("f00", self.player1).thenReturn(self.player2)
        self.assertEqual("tell Pl\\ayer\\1", self.render("tell <ARG:FIND_PLAYER:NAME>", data="f00"))

    def test_LAST_KILLER_name_with_backslashes(self):
        self.player2.kills(self.player1)
        self.assertEqual("tell Pl\\ayer\\1", self.render("tell <LAST_KILLER:NAME>"))

    def test_LAST_VICTIM_name_with_backslashes(self):
        self.player1.kills(self.player2)
        self.assertEqual("tell Pl\\ayer\\1", self.render("tell <LAST_VICTIM:NAME>"))


class Test_reg_commands_section(CustomcommandsTestCase):

    def load(self, conf_content):
        self.conf = CfgConfigParser()
        self.conf.loadFromString(dedent(conf_content))
        self.p = CustomcommandsPlugin(self.console, self.conf)
        self.p.onLoadConfig()
        self.p.onStartup()

    def test_reg_commands_section(self):
        self.load("""
            [reg commands]
            vip = say <PLAYER:NAME> is a VIP
        """)
        cmd = self.p._adminPlugin._commands.get('vip')
        self.assertIsNotNone(cmd)
        self.assertEqual(2, cmd.level[0])

    def test_regular_commands_section(self):
        self.load("""
            [regular commands]
            vip2 = say <PLAYER:NAME> is a VIP
        """)
        cmd = self.p._adminPlugin._commands.get('vip2')
        self.assertIsNotNone(cmd)
        self.assertEqual(2, cmd.level[0])
