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

import ftplib
import os

from unittest.mock import Mock, call, patch
from tests import B3TestCase
from b3.plugins.ftpytail import FtpytailPlugin


class FtpytailPluginTestCase(B3TestCase):

    def test_load_plugin(self):
        p = FtpytailPlugin(self.console)
        p.onLoadConfig()



class Test_reconnect(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        import tempfile, shutil
        self.tmpdir = tempfile.mkdtemp(prefix="b3_ftpytail")
        self.addCleanup(shutil.rmtree, self.tmpdir, True)
        self.p = FtpytailPlugin(self.console)
        self.p.onLoadConfig()
        self.p.lgame_log = os.path.join(self.tmpdir, 'games_mp.log')
        self.p.url_path = 'logs/games_mp.log'
        self.console.working = True
        self.addCleanup(setattr, self.console, 'working', False)

    def test_failed_reconnect_does_not_stop_b3(self):
        # GIVEN an FTP server that is unreachable for a while
        attempts = []

        def ftpconnect():
            attempts.append(self.console.working)
            if len(attempts) >= 4:
                # stop the test loop: B3 is shutting down
                self.console.working = False
            raise ConnectionRefusedError(111, 'Connection refused')

        self.p.ftpconnect = ftpconnect
        # WHEN
        with patch('b3.plugins.ftpytail.time.sleep') as sleep_mock:
            self.p.update()
        # THEN the plugin kept retrying instead of shutting down B3 after the first failure
        self.assertEqual([True, True, True, True], attempts)
        self.assertEqual(4, self.p._nbConsecutiveConnFailure)
        self.assertIn(call(self.p._short_delay), sleep_mock.call_args_list)

    def test_backoff_uses_long_delay_after_max_consecutive_failures(self):
        self.p._maxConsecutiveConnFailure = 2
        self.p._short_delay = 1
        self.p._long_delay = 15
        attempts = []

        def ftpconnect():
            attempts.append(1)
            if len(attempts) >= 4:
                self.console.working = False
            raise ftplib.error_temp('421 Service not available')

        self.p.ftpconnect = ftpconnect
        with patch('b3.plugins.ftpytail.time.sleep') as sleep_mock:
            self.p.update()
        delays = [c[0][0] for c in sleep_mock.call_args_list if c[0][0] in (1, 15)]
        self.assertEqual([1, 1, 15, 15], delays)

    def test_reconnects_after_transient_failure(self):
        # GIVEN a server which is down for the 2 first connection attempts
        ftp = Mock()
        ftp.size.return_value = 0
        calls = []

        def ftpconnect():
            calls.append(1)
            if len(calls) <= 2:
                raise OSError('timed out')
            self.console.working = False
            return ftp

        self.p.ftpconnect = ftpconnect
        with patch('b3.plugins.ftpytail.time.sleep'):
            self.p.update()
        self.assertEqual(3, len(calls))
        self.assertEqual(0, self.p._nbConsecutiveConnFailure)
        ftp.close.assert_called()
