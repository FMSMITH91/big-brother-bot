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
from tests.plugins.nickreg import NickregTestCase


class Test_crontab(NickregTestCase):

    def setUp(self):
        NickregTestCase.setUp(self)
        self.checked = []
        self.p.check_client_for_nick_steal = Mock(side_effect=self._fake_check)
        self.p.ignore_till = 0

    def _fake_check(self, client):
        self.checked.append(client)
        client.setvar(self.p, 'nick_check_time', self.console.time())

    def test_client_checked_again_after_interval(self):
        # GIVEN a first cron pass
        when(self.console).time().thenReturn(1000)
        self.p.execute_crontab()
        self.assertIn(self.guest, self.checked)
        self.checked[:] = []
        # WHEN the cron runs again once the interval elapsed
        when(self.console).time().thenReturn(1000 + self.p.interval + 2)
        self.p.execute_crontab()
        # THEN the client is checked again
        self.assertIn(self.guest, self.checked)

    def test_client_not_checked_again_too_soon(self):
        when(self.console).time().thenReturn(1000)
        self.p.execute_crontab()
        self.checked[:] = []
        when(self.console).time().thenReturn(1000 + 1)
        self.p.execute_crontab()
        self.assertNotIn(self.guest, self.checked)
