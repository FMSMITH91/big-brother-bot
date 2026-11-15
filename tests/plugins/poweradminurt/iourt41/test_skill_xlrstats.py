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
from b3.config import CfgConfigParser
from b3.plugins.poweradminurt import PoweradminurtPlugin
from tests.plugins.poweradminurt.iourt41 import Iourt41TestCase


class Test_skill_xlrstats_headshots(Iourt41TestCase):
    """
    The skill balancer must query xlrstats playerbody rows using the xlrstats player id
    and the ids of the bodyparts named after the parser's HL_HEAD / HL_HELMET hit locations.
    """

    def setUp(self):
        super(Test_skill_xlrstats_headshots, self).setUp()
        self.conf = CfgConfigParser()
        self.conf.loadFromString("""
[skillbalancer]
min_bal_interval: 1
        """)
        self.p = PoweradminurtPlugin(self.console, self.conf)
        self.init_default_cvar()
        self.p.onLoadConfig()
        self.p.onStartup()

        self.joe.connects("6")
        self.simon.connects("7")

        joe_stats = Mock(name='joe_stats', id=42, kills=100, ratio=1.5)
        simon_stats = Mock(name='simon_stats', id=43, kills=10, ratio=0.5)
        del joe_stats._new
        del simon_stats._new
        bodyparts = {}
        for name, bid in ((self.console.HL_HEAD, 7), (self.console.HL_HELMET, 8)):
            bp = Mock(name='bodypart_%s' % name, id=bid)
            del bp._new
            bodyparts[name] = bp
        body_kills = {(42, 7): 30, (42, 8): 10, (43, 7): 1, (43, 8): 0}

        self.xlrstats = Mock(name='xlrstats')
        self.xlrstats.get_PlayerStats.side_effect = lambda c: {self.joe: joe_stats, self.simon: simon_stats}[c]
        self.xlrstats.get_Bodypart.side_effect = lambda name: bodyparts[name]
        self.xlrstats.get_PlayerBody.side_effect = \
            lambda playerid, bodypartid: Mock(kills=body_kills.get((playerid, bodypartid), 0))
        when(self.console).getPlugin('xlrstats').thenReturn(self.xlrstats)

    def test_get_PlayerBody_uses_xlrstats_ids(self):
        self.p._getScores([self.joe, self.simon])
        self.assertSetEqual({(42, 7), (42, 8), (43, 7), (43, 8)},
                            {(c[1]['playerid'], c[1]['bodypartid']) for c in self.xlrstats.get_PlayerBody.call_args_list})
        self.xlrstats.get_Bodypart.assert_any_call(name=self.console.HL_HEAD)
        self.xlrstats.get_Bodypart.assert_any_call(name=self.console.HL_HELMET)

    def test_headshot_kills(self):
        self.assertEqual(40, self.p._getXlrstatsHeadshotKills(self.xlrstats, self.xlrstats.get_PlayerStats(self.joe)))

    def test_new_player_has_no_headshots(self):
        stats = Mock(id=None, _new=True)
        self.assertEqual(0, self.p._getXlrstatsHeadshotKills(self.xlrstats, stats))
        self.assertFalse(self.xlrstats.get_PlayerBody.called)
