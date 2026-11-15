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

from unittest.mock import Mock
from mockito import when
from b3 import TEAM_RED
from b3.events import Event
from tests import logging_disabled
from tests.plugins.poweradminbfbc2 import Poweradminbfbc2TestCase


class Test_teamId_is_int(Poweradminbfbc2TestCase):
    """
    The BFBC2 parser stores client.teamId as an int: make sure the plugin
    does not compare it against the string '1'.
    """

    def setUp(self):
        Poweradminbfbc2TestCase.setUp(self)
        self.console.write = Mock(name="write")
        with logging_disabled():
            from b3.fake import FakeClient
            self.joe = FakeClient(self.console, name="Joe", guid="joeguid", groupBits=1, team=TEAM_RED, teamId=1)
            self.admin = FakeClient(self.console, name="Admin", guid="adminguid", groupBits=128)
        self.joe.connects("Joe")
        self.admin.connects("Admin")

    def _move_calls(self):
        return [c[0][0] for c in self.console.write.call_args_list if c[0][0][0] == 'admin.movePlayer']

    def _assert_moved(self, client, newteam):
        self.assertListEqual([('admin.movePlayer', client.cid, newteam, 0, 'true')], self._move_calls())

    def test_balancer_moves_team1_player_to_team2(self):
        # GIVEN joe (teamId int 1) just joined team 1 which is now bigger
        self.joe.teamId = 1
        self.p._ignoreBalancingTill = 0
        when(self.console).getPlayerList().thenReturn({
            'Joe': {'teamId': '1'}, 'A': {'teamId': '1'}, 'B': {'teamId': '1'}, 'C': {'teamId': '2'}})
        # WHEN
        self.p.onClientTeamChange(Event(self.console.getEventID('EVT_CLIENT_TEAM_CHANGE'), data=None, client=self.joe))
        # THEN
        self._assert_moved(self.joe, '2')

    def test_balancer_moves_team2_player_to_team1(self):
        self.joe.teamId = 2
        self.p._ignoreBalancingTill = 0
        when(self.console).getPlayerList().thenReturn({
            'Joe': {'teamId': '2'}, 'A': {'teamId': '2'}, 'B': {'teamId': '2'}, 'C': {'teamId': '1'}})
        self.p.onClientTeamChange(Event(self.console.getEventID('EVT_CLIENT_TEAM_CHANGE'), data=None, client=self.joe))
        self._assert_moved(self.joe, '1')

    def test_cmd_pachangeteam_team1_player(self):
        self.joe.teamId = 1
        self.admin.says('!pachangeteam joe')
        self._assert_moved(self.joe, '2')

    def test_teambalance_with_str_teamId(self):
        # 3 players on team '1' (str), 1 on team 2 -> one must switch
        when(self.console).getPlayerList().thenReturn({
            'Joe': {'teamId': '1'}, 'A': {'teamId': '1'}, 'B': {'teamId': '1'}, 'C': {'teamId': '2'}})
        self.joe.teamId = '1'
        self.admin.teamId = 2
        self.p.teambalance()
        self.assertListEqual([('admin.movePlayer', self.joe.cid, 2, 0, 'true')], self._move_calls())
