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

from textwrap import dedent
from unittest.mock import Mock, patch, call

from b3.config import CfgConfigParser
from b3.plugins.punkbuster import PunkbusterPlugin
from tests import B3TestCase


class FakeCursor(object):

    def __init__(self, rows):
        self.rows = list(rows)

    @property
    def EOF(self):
        return not self.rows

    def getRow(self):
        return self.rows[0]

    def moveNext(self):
        self.rows.pop(0)

    def close(self):
        pass


ROWS = [
    {'time_add': 1400000000, 'pbid': 'a' * 32, 'name': 'Joë', 'ip': '11.22.33.44', 'reason': 'cheat'},
    {'time_add': 1400000001, 'pbid': 'b' * 32, 'name': 'Bob', 'ip': '22.33.44.55', 'reason': ''},
]


class Test_rebuild_bans_remote(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        self.conf = CfgConfigParser()
        self.conf.loadFromString(dedent("""
            [settings]
            bans_file: ftp://user:pass@127.0.0.1/pb/pbbans.dat
            rebuild_bans: 0
        """))
        self.p = PunkbusterPlugin(self.console, self.conf)
        self.p.onLoadConfig()
        self.assertTrue(self.p._remoteBansFile)
        self.console.storage = Mock()
        self.console.storage.query.return_value = FakeCursor(ROWS)
        self.console.write = Mock()
        self.uploaded = []

        def storbinary(cmd, fp, *args, **kwargs):
            # like the real ftplib: the data read from fp is sent with socket.sendall which requires bytes
            buf = fp.read()
            if not isinstance(buf, (bytes, bytearray)):
                raise TypeError("a bytes-like object is required, not '%s'" % type(buf).__name__)
            self.uploaded.append((cmd, bytes(buf)))

        self.ftp_patcher = patch('b3.plugins.punkbuster.ftplib.FTP')
        self.ftp_class = self.ftp_patcher.start()
        self.addCleanup(self.ftp_patcher.stop)
        self.ftp_class.return_value.storbinary.side_effect = storbinary

    def test_upload_bytes(self):
        # WHEN
        with patch.object(self.p, 'debug') as debug_mock:
            result = self.p.rebuild_bans()
        # THEN
        self.assertEqual(2, result)
        self.assertEqual(1, len(self.uploaded))
        cmd, data = self.uploaded[0]
        self.assertEqual('STOR /pb/pbbans.dat', cmd)
        self.assertIn('"Joë" "11.22.33.44" cheat'.encode('utf-8'), data)
        self.assertIn(b'"Bob" "22.33.44.55"', data)
        debug_mock.assert_any_call('uploaded pbbans.dat to FTP server successfully')
        self.console.write.assert_has_calls([call('PB_SV_BanEmpty'), call('PB_SV_BanLoad')])

    def test_upload_failure_is_not_reported_as_success(self):
        # GIVEN
        self.ftp_class.return_value.storbinary.side_effect = OSError('connection lost')
        # WHEN
        with patch.object(self.p, 'debug') as debug_mock, patch.object(self.p, 'error') as error_mock:
            result = self.p.rebuild_bans()
        # THEN
        self.assertIsNone(result)
        self.assertNotIn(call('uploaded pbbans.dat to FTP server successfully'), debug_mock.mock_calls)
        self.assertTrue(error_mock.called)
        self.assertFalse(self.console.write.called)
        self.ftp_class.return_value.quit.assert_called_once_with()

    def test_ftp_connection_failure(self):
        # GIVEN
        self.ftp_class.side_effect = ConnectionRefusedError(111, 'Connection refused')
        # WHEN
        result = self.p.rebuild_bans()
        # THEN
        self.assertIsNone(result)
        self.assertFalse(self.console.write.called)

    def test_cmd_pbbuildbans_reports_failure(self):
        self.ftp_class.return_value.storbinary.side_effect = OSError('connection lost')
        client = Mock()
        self.p.cmd_pbbuildbans(None, client)
        client.message.assert_called_once_with('^3PunkBuster: ^1failed to upload the ban file: check the B3 log')
