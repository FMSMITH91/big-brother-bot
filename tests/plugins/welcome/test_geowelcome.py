# BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2013 Thomas LEVEIL <courgette@bigbrotherbot.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

import b3

from unittest.mock import Mock
from mockito import when
from b3.config import CfgConfigParser
from b3.plugins.geowelcome import GeowelcomePlugin
from tests import B3TestCase, logging_disabled


class Test_geowelcome_and_welcome_plugin(B3TestCase):
    """
    The Geowelcome plugin replaces the Welcome plugin: it must only switch it off while it is enabled itself.
    """

    def setUp(self):
        B3TestCase.setUp(self)
        self.welcome = Mock()
        self.welcome.isEnabled.return_value = True
        when(self.console).getPlugin('admin').thenReturn(Mock())
        when(self.console).getPlugin('welcome').thenReturn(self.welcome)
        with logging_disabled():
            self.p = GeowelcomePlugin(self.console, CfgConfigParser())

    def test_enabled_geowelcome_disables_welcome(self):
        self.p.onStartup()
        self.welcome.disable.assert_called_once_with()

    def test_disabled_geowelcome_leaves_welcome_alone(self):
        # i.e: disabled_plugins: geowelcome (or its geolocation requirement)
        self.p.disable()
        self.p.onStartup()
        self.assertFalse(self.welcome.disable.called)

    def test_enabling_geowelcome_later_disables_welcome(self):
        self.p.disable()
        self.p.onStartup()
        self.p.enable()
        self.welcome.disable.assert_called_once_with()
