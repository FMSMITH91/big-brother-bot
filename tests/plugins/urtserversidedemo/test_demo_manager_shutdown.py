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
from tests.plugins.urtserversidedemo import PluginTestCase
from b3.fake import FakeClient


class Test_demo_manager_shutdown(PluginTestCase):
    CONF = """\
[commands]
startserverdemo = 20
"""

    def setUp(self):
        PluginTestCase.setUp(self)
        self.p.onStartup()
        self.p.stop_recording_all_players = Mock()
        self.joe = FakeClient(self.console, name="Joe", guid="01230123012301230123", groupBits=1)
        self.joe.connects('1')

    def test_shutdown_with_pending_autostop_timer(self):
        # GIVEN a pending auto-stop timer
        self.p.demo_manager._start_autostop_timer(self.joe, 3600)
        timer = self.p.demo_manager._auto_stop_timers[self.joe.guid]
        try:
            # WHEN B3 stops
            self.p.onStop(None)
            # THEN the timer is cancelled and forgotten
            timer.join(2)
            self.assertFalse(timer.is_alive())
            self.assertDictEqual({}, self.p.demo_manager._auto_stop_timers)
        finally:
            timer.cancel()

    def test_autostop_timer_is_daemon(self):
        self.p.demo_manager._start_autostop_timer(self.joe, 3600)
        timer = self.p.demo_manager._auto_stop_timers[self.joe.guid]
        try:
            self.assertTrue(timer.daemon)
        finally:
            timer.cancel()
