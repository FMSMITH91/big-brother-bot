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

import argparse
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

import b3
import b3.run


class Test_first_start(unittest.TestCase):
    """
    Windows pre-release test (2026-11-15): with the untouched sample b3.ini B3 stopped at once; the message must
    say which file to edit (and no longer send users to the defunct config.bigbrotherbot.net).
    """

    def test_sample_config_error_says_which_file_to_edit(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        config = os.path.join(folder, 'b3.ini')
        shutil.copy(b3.getAbsolutePath('@b3/conf/b3.distribution.ini'), config)
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            b3.run.run(argparse.Namespace(config=config))
        self.assertEqual(1, ctx.exception.code)
        self.assertIn('invalid parser specified in b3::parser (changeme)', out.getvalue())
        self.assertIn('Edit %s to fix this' % config, out.getvalue())

    def test_config_help_points_to_the_sample(self):
        text = b3.config_help()
        self.assertIn(b3.getAbsolutePath('@b3/conf/b3.distribution.ini'), text)
        self.assertIn(os.path.join(b3.HOMEDIR, 'b3.ini'), text)
        self.assertNotIn('bigbrotherbot.net', text)


if __name__ == '__main__':
    unittest.main()
