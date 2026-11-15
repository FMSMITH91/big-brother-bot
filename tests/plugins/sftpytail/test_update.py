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

import os
import shutil
import tempfile

from textwrap import dedent
from unittest.mock import Mock, patch

import paramiko

from b3.functions import splitDSN
from tests.plugins.sftpytail import Test_Sftpytail_plugin


class Test_update(Test_Sftpytail_plugin):
    """
    The tail thread must survive transient errors (file briefly missing during rotation, dropped socket).
    """

    def setUp(self):
        Test_Sftpytail_plugin.setUp(self)
        self.tmpdir = tempfile.mkdtemp(prefix="b3_sftpytail")
        self.addCleanup(shutil.rmtree, self.tmpdir, True)
        self.p.lgame_log = os.path.join(self.tmpdir, 'games_mp.log')
        self.p.sftpconfig = splitDSN('sftp://user:pass@localhost/logs/games_mp.log')
        self.console.working = True
        self.addCleanup(setattr, self.console, 'working', False)
        self.sleep_patcher = patch('b3.plugins.sftpytail.time.sleep')
        self.sleep_patcher.start()
        self.addCleanup(self.sleep_patcher.stop)

    def run_update(self, stat_results, max_iterations=None):
        """
        Run the update loop with a fake sFTP connection.
        :param stat_results: list of remote file sizes (int) or exceptions to raise from sftp.stat()
        """
        stat_results = list(stat_results)
        content = {'data': b''}
        sftp = Mock()
        opened = []

        def stat(path):
            result = stat_results.pop(0)
            if not stat_results:
                self.console.working = False
            if isinstance(result, BaseException):
                raise result
            content['data'] = b'x' * result
            return Mock(st_size=result)

        def sftp_open(path, mode):
            rfile = Mock()
            snapshot = content['data']
            pos = {'offset': 0}
            rfile.seek.side_effect = lambda offset: pos.__setitem__('offset', offset)
            rfile.read.side_effect = lambda: content['data'][pos['offset']:]
            opened.append((rfile, snapshot))
            return rfile

        sftp.stat.side_effect = stat
        sftp.open.side_effect = sftp_open
        connections = []

        def sftpconnect():
            connections.append(1)
            return Mock(), sftp

        self.p.sftpconnect = sftpconnect
        self.p.update()
        return connections, opened

    def test_survives_missing_file_during_rotation(self):
        # GIVEN the remote file disappears briefly (IOError ENOENT from stat) then comes back
        connections, _ = self.run_update([10, IOError(2, 'No such file'), 10, 20])
        # THEN the thread did not die and reconnected
        self.assertEqual(2, len(connections))

    def test_survives_dropped_socket(self):
        connections, _ = self.run_update([10, ConnectionResetError(104, 'Connection reset by peer'),
                                          EOFError(), 10])
        self.assertEqual(3, len(connections))

    def test_reopens_remote_file_on_rotation(self):
        # GIVEN the remote file grows, then is rotated (smaller size)
        connections, opened = self.run_update([100, 150, 20])
        # THEN the remote file was reopened after the rotation was detected
        self.assertEqual(1, len(connections))
        self.assertEqual(2, len(opened))
        self.assertTrue(opened[0][0].close.called)
        with open(self.p.lgame_log, 'rb') as f:
            self.assertTrue(f.read().endswith(b'x' * 70))


class Test_host_key_verification(Test_Sftpytail_plugin):

    def setUp(self):
        Test_Sftpytail_plugin.setUp(self)
        self.key = paramiko.RSAKey.generate(1024)
        self.host_keys = paramiko.HostKeys()
        self.p.get_host_keys = lambda: self.host_keys
        self.transport_patcher = patch('b3.plugins.sftpytail.paramiko.Transport')
        self.transport_class = self.transport_patcher.start()
        self.addCleanup(self.transport_patcher.stop)
        self.sftpclient_patcher = patch('b3.plugins.sftpytail.paramiko.SFTPClient')
        self.sftpclient_patcher.start()
        self.addCleanup(self.sftpclient_patcher.stop)

    def connect(self, dsn):
        self.p.sftpconfig = splitDSN(dsn)
        return self.p.sftpconnect()

    def test_refuse_unknown_host_key_by_default(self):
        self.p.onLoadConfig()
        with self.assertRaises(paramiko.SSHException) as ctx:
            self.connect('sftp://user:secret@myhost/logs/games_mp.log')
        self.assertIn('known_hosts', str(ctx.exception))
        self.assertFalse(self.transport_class.return_value.connect.called)

    def test_allow_unknown_host_key_option(self):
        self.conf.loadFromString(dedent("""
            [settings]
            allow_unknown_host_key: yes
        """))
        self.p.onLoadConfig()
        self.assertTrue(self.p.allow_unknown_host_key)
        self.connect('sftp://user:secret@myhost/logs/games_mp.log')
        self.transport_class.return_value.connect.assert_called_once_with(
            username='user', password='secret', hostkey=None)

    def test_allow_unknown_host_key_default_off(self):
        self.conf.loadFromString(dedent("""
            [settings]
        """))
        self.p.onLoadConfig()
        self.assertFalse(self.p.allow_unknown_host_key)

    def test_known_host_standard_port(self):
        self.p.onLoadConfig()
        self.host_keys.add('myhost', self.key.get_name(), self.key)
        self.connect('sftp://user:secret@myhost/logs/games_mp.log')
        self.transport_class.return_value.connect.assert_called_once_with(
            username='user', password='secret', hostkey=self.key)

    def test_known_host_non_standard_port(self):
        # OpenSSH stores keys of hosts on non standard ports as '[host]:port'
        self.p.onLoadConfig()
        self.host_keys.add('[myhost]:2222', self.key.get_name(), self.key)
        self.connect('sftp://user:secret@myhost:2222/logs/games_mp.log')
        self.transport_class.return_value.connect.assert_called_once_with(
            username='user', password='secret', hostkey=self.key)

    def test_key_for_other_port_not_used(self):
        self.p.onLoadConfig()
        self.host_keys.add('[myhost]:2222', self.key.get_name(), self.key)
        with self.assertRaises(paramiko.SSHException):
            self.connect('sftp://user:secret@myhost:2223/logs/games_mp.log')
        self.assertFalse(self.transport_class.return_value.connect.called)
