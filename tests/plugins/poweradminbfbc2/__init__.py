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

import unittest

from mockito import when
from textwrap import dedent
from b3.config import CfgConfigParser
from b3.config import XmlConfigParser
from b3.plugins.admin import AdminPlugin
from b3.plugins.poweradminbfbc2 import Poweradminbfbc2Plugin
from tests import logging_disabled


class Poweradminbfbc2TestCase(unittest.TestCase):

    def setUp(self):
        self.parser_conf = XmlConfigParser()
        self.parser_conf.loadFromString(r"""<configuration/>""")
        with logging_disabled():
            from b3.fake import FakeConsole
            self.console = FakeConsole(self.parser_conf)

        with logging_disabled():
            self.adminPlugin = AdminPlugin(self.console, '@b3/conf/plugin_admin.ini')
            self.adminPlugin._commands = {}
            self.adminPlugin.onStartup()

        when(self.console).getPlugin('admin').thenReturn(self.adminPlugin)

        self.conf = CfgConfigParser()
        self.conf.loadFromString(dedent("""
            [commands]
            pachangeteam-ct: fulladmin
            [teambalancer]
            enabled: yes
        """))
        with logging_disabled():
            self.p = Poweradminbfbc2Plugin(self.console, self.conf)
            self.p.onLoadConfig()
            self.p.onStartup()
