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
from b3.parsers.altitude import AltitudeParser


class Test_OnAltitudeCommandVote(unittest.TestCase):

    def test_vote_command(self):
        # GIVEN
        console = Mock()
        joe = Mock()
        console.clients.getByGUID = Mock(return_value=joe)
        altitude_event = {"port": 27276, "time": 3250286, "arguments": ["kick", "Courgette"],
                          "source": "c0aaf37d-e56d-4431-aa1e-69d5e18be5e6", "command": "vote",
                          "group": "Anonymous", "type": "consoleCommandExecute"}
        # WHEN
        AltitudeParser.OnAltitudeCommandVote(console, altitude_event)
        # THEN
        console.clients.getByGUID.assert_called_once_with("c0aaf37d-e56d-4431-aa1e-69d5e18be5e6")
        console.getEvent.assert_called_once_with("EVT_CLIENT_CALL_VOTE", data=altitude_event, client=joe)
