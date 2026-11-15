# -*- coding: utf-8 -*-

# ################################################################### #
#                                                                     #
#  BigBrotherBot(B3) (www.bigbrotherbot.net)                          #
#                                                                     #
#  This program is free software; you can redistribute it and/or      #
#  modify it under the terms of the GNU General Public License        #
#  as published by the Free Software Foundation; either version 2     #
#  of the License, or (at your option) any later version.             #
#                                                                     #
# ################################################################### #

from textwrap import dedent
from unittest.mock import patch
from tests import B3TestCase
from b3.plugins.status import StatusPlugin
from b3.config import CfgConfigParser


class Test_storeServerinfo(B3TestCase):

    @patch("b3.cron.PluginCronTab")
    def setUp(self, pluginCronTab_mock):
        B3TestCase.setUp(self)
        conf = CfgConfigParser()
        conf.loadFromString(dedent(r"""
            [settings]
            interval: 60
            output_file: ~/status.xml
            enableDBsvarSaving: yes
            enableDBclientSaving: no
            """))
        self.p = StatusPlugin(self.console, conf)
        self.p.onLoadConfig()
        self.p.onStartup()  # the test console uses SQLite

    def svar(self, name):
        cursor = self.console.storage.query("SELECT value FROM %s WHERE name = '%s'" % (self.p._tables['svars'], name))
        return None if cursor.EOF else cursor.getRow()['value']

    def test_insert_then_update_on_sqlite(self):
        # previously used MySQL-only ON DUPLICATE KEY UPDATE, which fails on SQLite
        self.p.storeServerinfo('sv_hostname', 'first')
        self.p.storeServerinfo('sv_hostname', 'second')
        self.assertEqual('second', self.svar('sv_hostname'))

    def test_quotes_and_backslashes_are_kept(self):
        value = "Joe's \\ \"server\" \\"
        self.p.storeServerinfo('sv_hostname', value)
        self.assertEqual(value, self.svar('sv_hostname'))


class Test_client_storage(B3TestCase):

    @patch("b3.cron.PluginCronTab")
    def setUp(self, pluginCronTab_mock):
        B3TestCase.setUp(self)
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        conf = CfgConfigParser()
        conf.loadFromString(dedent(r"""
            [settings]
            interval: 60
            output_file: %s/status.xml
            enableDBsvarSaving: no
            enableDBclientSaving: yes
            """ % self.tmpdir))
        self.p = StatusPlugin(self.console, conf)
        self.p.onLoadConfig()
        self.p.onStartup()  # the test console uses SQLite

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        B3TestCase.tearDown(self)

    def test_player_name_with_quotes_is_stored(self):
        # the client row used to be written with only ' backslash-escaped, which SQLite and PostgreSQL reject
        from b3.fake import FakeClient
        name = "O'Neil \\ \"x\""
        joe = FakeClient(self.console, name=name, guid="joeguid")
        joe.connects('1')
        self.p.update()
        cursor = self.console.storage.query("SELECT * FROM %s" % self.p._tables['cvars'])
        rows = []
        while not cursor.EOF:
            rows.append(cursor.getRow())
            cursor.moveNext()
        cursor.close()
        self.assertIn(name, [row.get('Name') for row in rows])
