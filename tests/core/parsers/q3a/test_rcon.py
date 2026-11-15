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

from textwrap import dedent
from unittest.mock import Mock, patch
from b3.config import CfgConfigParser, MainConfig
from b3.parsers.q3a.rcon import Rcon


class Test_status_cache(unittest.TestCase):

    def setUp(self):
        conf = CfgConfigParser()
        conf.loadFromString(dedent("""
            [caching]
            status_cache_type: memory
            status_cache_expire: 2
        """))
        self.console = Mock()
        self.console.config = MainConfig(conf)
        # do not start the background writer thread
        with patch('b3.parsers.q3a.rcon._thread.start_new_thread'):
            self.rcon = Rcon(self.console, ('127.0.0.1', 27960), 'password')
        self.rcon.sendRcon = Mock(return_value='map: ut4_casa\n')

    def tearDown(self):
        self.rcon.socket.close()

    def test_first_status_is_fetched_from_the_server(self):
        self.assertTrue(self.rcon.status_cache)
        self.assertEqual('map: ut4_casa\n', self.rcon.write('status'))
        self.assertEqual(1, self.rcon.sendRcon.call_count)

    def test_second_status_is_served_from_the_cache(self):
        self.rcon.write('status')
        self.assertEqual('map: ut4_casa\n', self.rcon.write('status'))
        self.assertEqual(1, self.rcon.sendRcon.call_count)
