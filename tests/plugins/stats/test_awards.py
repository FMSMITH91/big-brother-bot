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

from unittest.mock import patch, call
from tests.plugins.stats import StatPluginTestCase


class Test_onShowAwards(StatPluginTestCase):

    def setUp(self):
        StatPluginTestCase.setUp(self)
        self.p.show_awards = True
        self.p.show_awards_xp = True

    def test_no_data(self):
        # GIVEN nobody has points nor experience yet
        with patch.object(self.console, "say") as say_mock:
            # WHEN
            self.p.onShowAwards(None)
        # THEN no crash and nothing to announce
        self.assertListEqual([], say_mock.mock_calls)

    def test_with_data(self):
        # GIVEN
        self.joe.kills(self.mike)
        with patch.object(self.console, "say") as say_mock:
            # WHEN
            self.p.onShowAwards(None)
        # THEN
        self.assertEqual(2, say_mock.call_count, say_mock.mock_calls)
        self.assertTrue(say_mock.mock_calls[0][1][0].startswith('^3Top Stats:^7 ^3#1^7 '))
        self.assertIn('Joe', say_mock.mock_calls[0][1][0])
        self.assertTrue(say_mock.mock_calls[1][1][0].startswith('^3Top Experienced Players:^7 ^3#1^7 '))
