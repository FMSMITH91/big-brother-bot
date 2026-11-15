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

import b3


class Test_term_signal_handler(unittest.TestCase):

    def test_requested_stop_exits_with_status_0(self):
        # live CoD1 test (2026-11-15): B3 exited with 222 on SIGTERM, so systemd marked the service as failed
        console = Mock()
        handler = b3.term_signal_handler(console)
        with self.assertRaises(SystemExit) as ctx:
            handler(15, None)
        self.assertEqual(0, ctx.exception.code)
        console.shutdown.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
