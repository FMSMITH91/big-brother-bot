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

import http.client
import os
import shutil
import tempfile
import urllib.error

from unittest.mock import Mock, patch
from b3.plugins.cod7http import Cod7HttpPlugin
from tests import B3TestCase


class Test_processData(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        self.tmpdir = tempfile.mkdtemp(prefix="b3_cod7http")
        self.addCleanup(shutil.rmtree, self.tmpdir, True)
        self.p = Cod7HttpPlugin(self.console)
        self.p._url = 'http://127.0.0.1:1/games_mp.log'
        self.p.timeout = 0
        self.p.locallog = os.path.join(self.tmpdir, 'games_mp.log')
        self.console.working = True
        self.addCleanup(setattr, self.console, 'working', False)
        patcher = patch('b3.plugins.cod7http.time.sleep')
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_with_errors(self, *errors):
        """
        make urlopen raise the given errors, then succeed once and stop the loop
        """
        errors = list(errors)
        calls = []

        def urlopen(request):
            calls.append(request)
            if errors:
                raise errors.pop(0)
            self.console.working = False
            response = Mock()
            response.read.return_value = b'line 1\r\nline 2\r\n'
            response.info.return_value = {}
            return response

        with patch('b3.plugins.cod7http.urllib.request.urlopen', side_effect=urlopen):
            self.p.processData()
        return calls

    def test_retry_after_http_error(self):
        calls = self.run_with_errors(urllib.error.URLError('down'))
        self.assertEqual(2, len(calls))

    def test_retry_after_connection_reset(self):
        calls = self.run_with_errors(ConnectionResetError(104, 'Connection reset by peer'))
        self.assertEqual(2, len(calls))

    def test_retry_after_remote_disconnected(self):
        calls = self.run_with_errors(http.client.RemoteDisconnected('Remote end closed connection without response'))
        self.assertEqual(2, len(calls))

    def test_retry_after_incomplete_read(self):
        calls = self.run_with_errors(http.client.IncompleteRead(b'partial'), ConnectionRefusedError(111, 'refused'))
        self.assertEqual(3, len(calls))
        # the successful download was written to the local log
        self.assertTrue(os.path.isfile(self.p.locallog))
