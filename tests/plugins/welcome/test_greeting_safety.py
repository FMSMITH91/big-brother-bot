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

import re

from unittest.mock import patch, call
from b3.plugins.welcome import F_CUSTOM_GREETING
from b3.fake import FakeClient
from tests.plugins.welcome import Welcome_functional_test


class Test_greeting_rendering(Welcome_functional_test):

    def setUp(self):
        Welcome_functional_test.setUp(self)
        self.load_config()
        self.p.onEvent = lambda *args, **kwargs: None
        self.client = FakeClient(console=self.console, name="Jack", guid="JackGUID")
        self.client._connections = 2
        self.client.connects("0")
        self.client.says("!register")
        self.p._welcomeFlags = F_CUSTOM_GREETING
        self.say_patcher = patch.object(self.console, "say")
        self.say_mock = self.say_patcher.start()

    def tearDown(self):
        Welcome_functional_test.tearDown(self)
        self.say_patcher.stop()

    def test_greeting_with_maxLevel_is_shown(self):
        # GIVEN a greeting set with $maxLevel (accepted by !greeting)
        self.client.greeting = '|%(maxLevel)s|'
        # WHEN
        self.p.welcome(self.client)
        # THEN
        self.assertListEqual([call('^7Jack^7^7 joined: |1|')], self.say_mock.mock_calls)

    def test_greeting_set_by_command_with_every_variable_is_shown(self):
        self.superadmin.connects("1")
        self.superadmin.says('!greeting $name $maxLevel $group $connections')
        self.superadmin.lastVisit = None
        self.p.welcome(self.superadmin)
        self.assertListEqual([call('^7SuperAdmin^7^7 joined: %s 100 Super Admin %s' % (
            self.superadmin.exactName, self.superadmin.connections))], self.say_mock.mock_calls)

    def test_stored_greeting_with_width_specifier_is_not_padded(self):
        # GIVEN a malicious greeting stored before the fix
        self.client.greeting = 'x%(name)50sx'
        # WHEN
        self.p.welcome(self.client)
        # THEN
        self.assertListEqual([call('^7Jack^7^7 joined: x%(name)50sx')], self.say_mock.mock_calls)

    def test_render_greeting_huge_width(self):
        rendered = self.p.render_greeting('%(name)999999999s', {'name': 'Jack'})
        self.assertEqual('%(name)999999999s', rendered)

    def test_render_greeting_unknown_variable_and_percent(self):
        self.assertEqual('100% %(id)s Jack', self.p.render_greeting('100%% %(id)s %(name)s', {'name': 'Jack'}))


class Test_cmd_greeting_safety(Welcome_functional_test):

    def setUp(self):
        Welcome_functional_test.setUp(self)
        self.load_config()
        self.superadmin.connects("2")
        self.superadmin.greeting = 'f00'
        self.superadmin.clearMessageHistory()

        # FakeClient.message() %-formats its text, real parsers send it as is: mimic the real behavior
        # so messages containing a literal '%' can be checked
        def message(msg, *args):
            self.superadmin.message_history.append(re.sub(r'\^[0-9]', '', msg % args if args else msg).strip())
        self.superadmin.message = message

    def test_width_specifier_is_not_interpreted(self):
        # WHEN
        self.superadmin.says('!greeting %(name)50s')
        # THEN
        self.assertListEqual(['Greeting Test: %(name)50s', 'Greeting changed to: %(name)50s'],
                             self.superadmin.message_history)
        self.assertEqual('%%(name)50s', self.superadmin.greeting)

    def test_literal_percent(self):
        self.superadmin.says('!greeting 100% $name')
        self.assertListEqual(['Greeting Test: 100% SuperAdmin', 'Greeting changed to: 100% $name'],
                             self.superadmin.message_history)
        self.assertEqual('100%% %(name)s', self.superadmin.greeting)

    def test_greeting_too_long_after_escaping(self):
        self.superadmin.says('!greeting %s' % ('%' * 200))
        self.assertListEqual(['Your greeting is too long'], self.superadmin.message_history)
        self.assertEqual('f00', self.superadmin.greeting)
