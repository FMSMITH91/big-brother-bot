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


class Test_sanitize_rcon_arg(unittest.TestCase):

    def test_sanitize(self):
        from b3.parsers.source.rcon import sanitize_rcon_arg
        self.assertEqual("a:b'c d e f", sanitize_rcon_arg('a;b"c\nd\re\x00f'))
        self.assertEqual('', sanitize_rcon_arg(None))
        self.assertEqual('12', sanitize_rcon_arg(12))
        self.assertEqual('étoilé àÄ', sanitize_rcon_arg('étoilé àÄ'))

    def test_quote(self):
        from b3.parsers.source.rcon import quote_rcon_arg
        self.assertEqual('"x\': quit"', quote_rcon_arg('x"; quit'))
