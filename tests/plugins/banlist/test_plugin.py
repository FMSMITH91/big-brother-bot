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

import gzip
import http.server
import os
import shutil
import tempfile
import threading

from unittest.mock import Mock, patch
from mockito import when, unstub
from b3.config import XmlConfigParser
from b3.plugins.admin import AdminPlugin
import b3.plugins.banlist as banlist_module
from b3.plugins.banlist import BanlistPlugin, IpBanlist
from tests import B3TestCase, logging_disabled


class BanlistPluginTestCase(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        self.addCleanup(unstub)
        self.tmpdir = tempfile.mkdtemp(prefix="b3_banlist")
        self.addCleanup(shutil.rmtree, self.tmpdir, True)
        with logging_disabled():
            self.adminPlugin = AdminPlugin(self.console, '@b3/conf/plugin_admin.ini')
            self.adminPlugin.onLoadConfig()
            self.adminPlugin.onStartup()
        when(self.console).getPlugin('admin').thenReturn(self.adminPlugin)

    def write_file(self, name, content=''):
        path = os.path.join(self.tmpdir, name)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def load_plugin(self, xml):
        conf = XmlConfigParser()
        conf.loadFromString(xml)
        self.p = BanlistPlugin(self.console, conf)
        self.p.onLoadConfig()
        self.p.onStartup()
        return self.p


class Test_auto_update_crontab(BanlistPluginTestCase):

    def setUp(self):
        BanlistPluginTestCase.setUp(self)
        self.ip_file = self.write_file('ip.txt', '11.22.33.44\n')
        self.guid_file = self.write_file('guid.txt', 'ABCDEF\n')
        # the files are fresh: no download is attempted on load
        self.xml = r"""
            <configuration plugin="banlist">
                <settings name="global_settings">
                    <set name="auto_update">yes</set>
                </settings>
                <ip_banlist>
                    <name>ip list</name>
                    <file>%s</file>
                    <url>http://127.0.0.1:1/ip.txt</url>
                </ip_banlist>
                <guid_whitelist>
                    <name>guid whitelist</name>
                    <file>%s</file>
                    <url>http://127.0.0.1:1/guid.txt</url>
                </guid_whitelist>
            </configuration>
        """ % (self.ip_file, self.guid_file)

    def banlist_tabs(self):
        return [t for t in self.console.cron._tabs.values() if getattr(t, 'plugin', None) is self.p]

    def test_crontabs_survive_startup(self):
        # WHEN
        self.load_plugin(self.xml)
        # THEN
        tabs = self.banlist_tabs()
        self.assertEqual(2, len(tabs))
        self.assertIn(id(self.p._banlists[0]._cronTab), self.console.cron._tabs)
        self.assertIn(id(self.p._whitelists[0]._cronTab), self.console.cron._tabs)

    def test_reconfig_does_not_duplicate_crontabs(self):
        # GIVEN
        self.load_plugin(self.xml)
        # WHEN
        self.p.onLoadConfig()
        self.p.onLoadConfig()
        # THEN
        self.assertEqual(2, len(self.banlist_tabs()))
        self.assertIn(id(self.p._banlists[0]._cronTab), self.console.cron._tabs)


class Test_optional_message(BanlistPluginTestCase):

    def test_kick_without_message_does_not_abort_checks(self):
        # GIVEN a banlist without <message>
        ip_file = self.write_file('ip.txt', '11.22.33.44\n22.33.44.55\n')
        self.load_plugin(r"""
            <configuration plugin="banlist">
                <ip_banlist>
                    <name>ip list</name>
                    <file>%s</file>
                </ip_banlist>
            </configuration>
        """ % ip_file)
        self.assertIsNone(self.p._banlists[0].message)
        joe = Mock(cid='1', id=1, ip='11.22.33.44', guid='JOE', pbid='', maxLevel=0)
        joe.name = 'Joe'
        bill = Mock(cid='2', id=2, ip='22.33.44.55', guid='BILL', pbid='', maxLevel=0)
        bill.name = 'Bill'
        self.console.write = Mock()
        # WHEN
        with patch.object(self.console.clients, 'getList', return_value=[joe, bill]):
            self.p.checkConnectedPlayers()
        # THEN both players have been checked and kicked
        self.assertTrue(joe.kick.called)
        self.assertTrue(bill.kick.called)
        self.assertFalse(self.console.write.called)

    def test_getMessage_without_message(self):
        ip_file = self.write_file('ip.txt', '')
        self.load_plugin(r"""
            <configuration plugin="banlist">
                <ip_banlist>
                    <name>ip list</name>
                    <file>%s</file>
                    <message></message>
                </ip_banlist>
            </configuration>
        """ % ip_file)
        self.assertEqual('', self.p._banlists[0].getMessage(Mock()))


class Test_cmd_banlistinfo(BanlistPluginTestCase):

    def setUp(self):
        BanlistPluginTestCase.setUp(self)
        self.load_plugin(r"""
            <configuration plugin="banlist">
                <ip_banlist>
                    <name>ip list</name>
                    <file>%s</file>
                    <force_ip_range>yes</force_ip_range>
                </ip_banlist>
                <guid_banlist>
                    <name>guid list</name>
                    <file>%s</file>
                </guid_banlist>
            </configuration>
        """ % (self.write_file('ip.txt'), self.write_file('guid.txt')))

    def test_force_ip_range(self):
        client = Mock()
        self.p.cmd_banlistinfo('0 force_ip_range', client)
        client.message.assert_called_once_with('True')

    def test_force_ip_range_on_guid_banlist(self):
        client = Mock()
        self.p.cmd_banlistinfo('1 force_ip_range', client)
        client.message.assert_called_once_with('n/a')

    def test_name(self):
        client = Mock()
        self.p.cmd_banlistinfo('1 name', client)
        client.message.assert_called_once_with('guid list')


class _Handler(http.server.BaseHTTPRequestHandler):

    body = b''
    headers_to_send = {}

    def do_GET(self):
        self.send_response(200)
        for k, v in self.headers_to_send.items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


class Test_download_limits(BanlistPluginTestCase):

    def setUp(self):
        BanlistPluginTestCase.setUp(self)
        self.server = http.server.HTTPServer(('127.0.0.1', 0), _Handler)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.shutdown)
        self.url = 'http://127.0.0.1:%s/banlist.txt' % self.server.server_address[1]
        self.file = self.write_file('ip.txt', '')
        os.utime(self.file, (0, 0))  # old file
        plugin = Mock()
        plugin._auto_update = False
        import xml.etree.ElementTree as ET
        self.banlist = IpBanlist(plugin, ET.fromstring(r"""
            <ip_banlist>
                <name>remote</name>
                <file>%s</file>
                <url>%s</url>
            </ip_banlist>
        """ % (self.file, self.url)))

    def serve(self, body, headers=None):
        _Handler.body = body
        _Handler.headers_to_send = headers or {}

    def read_file(self):
        with open(self.file, 'rb') as f:
            return f.read()

    def test_download(self):
        self.serve(b'11.22.33.44\n')
        self.assertIs(True, self.banlist.updateFromUrl())
        self.assertEqual(b'11.22.33.44\n', self.read_file())

    def test_download_gzip(self):
        self.serve(gzip.compress(b'11.22.33.44\n'), {'Content-Encoding': 'gzip'})
        self.assertIs(True, self.banlist.updateFromUrl())
        self.assertEqual(b'11.22.33.44\n', self.read_file())

    def test_download_too_big(self):
        self.serve(b'1' * 2048)
        with patch.object(banlist_module, 'MAX_BANLIST_SIZE', 1024):
            result = self.banlist.updateFromUrl()
        self.assertIsNot(True, result)
        self.assertIn('too big', result)
        self.assertEqual(b'', self.read_file())

    def test_gzip_bomb(self):
        self.serve(gzip.compress(b'\0' * (1024 * 1024)), {'Content-Encoding': 'gzip'})
        with patch.object(banlist_module, 'MAX_BANLIST_SIZE', 64 * 1024):
            result = self.banlist.updateFromUrl()
        self.assertIsNot(True, result)
        self.assertIn('too big', result)
        self.assertEqual(b'', self.read_file())

    def test_timeout(self):
        with patch('urllib.request.OpenerDirector.open') as open_mock:
            open_mock.side_effect = TimeoutError('timed out')
            result = self.banlist.updateFromUrl()
        self.assertEqual('timed out', result)
        self.assertEqual(banlist_module.DOWNLOAD_TIMEOUT, open_mock.call_args[1].get('timeout'))
