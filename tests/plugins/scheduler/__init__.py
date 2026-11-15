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

from mockito import when
from b3.config import XmlConfigParser
from b3.plugins.scheduler import SchedulerPlugin
from tests import B3TestCase


class SchedulerTestCase(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        self.p = None
        when(self.console.config).get('b3', 'time_zone').thenReturn('GMT')

    def tearDown(self):
        if self.p and self.p._tasks:
            for t in self.p._tasks:
                t.cancel()
        B3TestCase.tearDown(self)

    def load_plugin(self, xml):
        conf = XmlConfigParser()
        conf.loadFromString(xml)
        self.p = SchedulerPlugin(self.console, conf)
        self.p.onLoadConfig()
        return self.p
