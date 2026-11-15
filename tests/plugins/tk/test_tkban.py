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

from unittest.mock import Mock, patch
from tests.plugins.tk import Tk_functional_test


@patch("threading.Timer")
class Test_checkTKBan(Tk_functional_test):

    def setUp(self):
        Tk_functional_test.setUp(self)
        self.p._round_grace = 0
        self.joe.connects(0)
        self.mike.connects(1)
        self.bill.connects(2)
        self.joe.tempban = Mock()

    def _attack(self, attacker, victim, points):
        self.p.getClientTkInfo(attacker).damage(victim.cid, points)
        self.p.getClientTkInfo(victim).damaged(attacker.cid, points)

    def test_ban_duration_multiplied_by_number_of_victims(self, timer_patch):
        # GIVEN joe (level 1, ban_length 2) attacked 2 team mates beyond max_points
        self._attack(self.joe, self.mike, 300)
        self._attack(self.joe, self.bill, 300)
        self.assertGreaterEqual(self.p.getClientTkInfo(self.joe).points, self.p._maxPoints)
        # WHEN
        self.p.checkTKBan(self.joe)
        # THEN
        self.assertEqual(1, self.joe.tempban.call_count)
        self.assertEqual(2 * 2, self.joe.tempban.call_args[0][2])
        # and joe got forgiven by everybody
        self.assertDictEqual({}, self.p.getClientTkInfo(self.joe).attacked)
        self.assertDictEqual({}, self.p.getClientTkInfo(self.mike).attackers)
        self.assertDictEqual({}, self.p.getClientTkInfo(self.bill).attackers)

    def test_ban_duration_single_victim(self, timer_patch):
        self._attack(self.joe, self.mike, 500)
        self.p.checkTKBan(self.joe)
        self.assertEqual(2, self.joe.tempban.call_args[0][2])


class Test_getMultipliers(Tk_functional_test):

    def setUp(self):
        Tk_functional_test.setUp(self)
        self.p._round_grace = 0

    def test_levels_in_descending_order(self):
        # GIVEN levels listed in descending order in the config
        self.p._levels = {
            40: (0.75, 0.5, 0),
            20: (1.0, 0.5, 0),
            2: (1.0, 0.5, 1),
            0: (2.0, 1.0, 2),
        }
        self.joe.connects(0)        # level 1
        self.superadmin.connects(1)  # level 100
        # THEN
        self.assertEqual((2.0, 1.0, 2), self.p.getMultipliers(self.joe))
        self.assertEqual((0.75, 0.5, 0), self.p.getMultipliers(self.superadmin))

    def test_levels_in_ascending_order(self):
        self.p._levels = {
            0: (2.0, 1.0, 2),
            2: (1.0, 0.5, 1),
            20: (1.0, 0.5, 0),
            40: (0.75, 0.5, 0),
        }
        self.joe.connects(0)
        self.superadmin.connects(1)
        self.assertEqual((2.0, 1.0, 2), self.p.getMultipliers(self.joe))
        self.assertEqual((0.75, 0.5, 0), self.p.getMultipliers(self.superadmin))

    def test_levels_loaded_from_config_in_descending_order(self):
        self.conf.set('settings', 'levels', '40,20,2,1,0')
        self.p.onLoadConfig()
        self.p._round_grace = 0
        self.assertListEqual([40, 20, 2, 1, 0], list(self.p._levels.keys()))
        self.joe.connects(0)
        self.superadmin.connects(1)
        self.assertEqual((2.0, 1.0, 2), self.p.getMultipliers(self.joe))
        self.assertEqual((0.75, 0.5, 0), self.p.getMultipliers(self.superadmin))
