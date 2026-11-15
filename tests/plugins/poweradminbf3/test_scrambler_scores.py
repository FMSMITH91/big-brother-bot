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
from unittest.mock import Mock

from b3.parsers.frostbite2.util import PlayerInfoBlock
from b3.plugins.poweradminbf3 import Scrambler


class Test_Scrambler_by_scores(unittest.TestCase):

    def setUp(self):
        self.plugin = Mock(name='plugin')
        self.clients = [Mock(name=n, cid=n) for n in ('A', 'B', 'C')]
        self.plugin.console.clients.getList.side_effect = lambda: list(self.clients)
        self.scrambler = Scrambler(self.plugin)
        self.scrambler.setStrategy('score')

    def test_scores_are_sorted_numerically(self):
        # GIVEN scores as sent by the server (strings)
        self.scrambler.onRoundOverTeamScores(PlayerInfoBlock(['2', 'name', 'score', '3',
                                                              'A', '100',
                                                              'B', '20',
                                                              'C', '5']))
        # WHEN
        sorted_clients = self.scrambler._getClients_by_scores()
        # THEN
        self.assertListEqual(['C', 'B', 'A'], [c.cid for c in sorted_clients])
