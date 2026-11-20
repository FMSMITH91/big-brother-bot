# -*- coding: utf-8 -*-
"""
The pingwatch plugin (in the default b3.ini) had no tests.
"""
import b3

from mockito import when
from b3.config import CfgConfigParser
from b3.fake import FakeClient
from b3.plugins.admin import AdminPlugin
from b3.plugins.pingwatch import PingwatchPlugin
from tests import B3TestCase, logging_disabled


class Pingwatch_test(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        with logging_disabled():
            self.adminPlugin = AdminPlugin(self.console, '@b3/conf/plugin_admin.ini')
            when(self.console).getPlugin('admin').thenReturn(self.adminPlugin)
            self.adminPlugin.onLoadConfig()
            self.adminPlugin.onStartup()
            self.conf = CfgConfigParser()
            self.conf.load(b3.getAbsolutePath('@b3/conf/plugin_pingwatch.ini'))
            self.p = PingwatchPlugin(self.console, self.conf)
            self.p.onLoadConfig()
            self.p.onStartup()
        self.now = 10000
        self.console.time = lambda: self.now
        self.p._ignoreTill = 0
        self.joe = FakeClient(self.console, name='Joe', guid='joeguid', groupBits=1)
        self.bill = FakeClient(self.console, name='Bill', guid='billguid', groupBits=1)
        self.mod = FakeClient(self.console, name='Mod', guid='modguid', groupBits=8)
        for c, cid in ((self.joe, '1'), (self.bill, '2'), (self.mod, '3')):
            c.connects(cid)
        self.said = []
        self.console.say = lambda msg, *args: self.said.append(msg)
        self.pings = {}
        self.console.getPlayerPings = lambda *a, **k: dict(self.pings)

    def test_default_config(self):
        self.assertEqual((30, 500, 90), (self.p._interval, self.p._maxPing, self.p._maxPingDuration))

    def test_low_ping_is_ignored(self):
        self.pings = {'1': 100}
        self.p.check()
        self.assertFalse(self.joe.isvar(self.p, 'highping'))
        self.assertEqual([], self.said)

    def test_high_ping_announced_after_the_duration(self):
        self.pings = {'1': 800}
        self.p.check()  # starts watching
        self.assertTrue(self.joe.isvar(self.p, 'highping'))
        self.now += 60
        self.p.check()  # not long enough yet
        self.assertEqual([], self.said)
        self.now += 31
        self.p.check()
        self.assertEqual(['^7Joe ^7ping detected as too high 800'], self.said)

    def test_ci_ping(self):
        self.pings = {'1': 999}
        self.p.check()
        self.now += 91
        self.p.check()
        self.assertEqual(['^7Joe ^7ping detected as Connection Interrupted (CI)'], self.said)

    def test_every_high_ping_player_is_watched_in_one_pass(self):
        # check() used to return after marking the first player
        self.pings = {'1': 800, '2': 900}
        self.p.check()
        self.assertTrue(self.joe.isvar(self.p, 'highping'))
        self.assertTrue(self.bill.isvar(self.p, 'highping'))

    def test_watch_resets_when_the_ping_recovers(self):
        # the mark was never cleared, so a single later spike was announced at once
        self.pings = {'1': 800}
        self.p.check()
        self.pings = {'1': 80}
        self.now += 10
        self.p.check()
        self.assertFalse(self.joe.isvar(self.p, 'highping'))
        self.now += 500
        self.pings = {'1': 800}
        self.p.check()
        self.assertEqual([], self.said)

    def test_ignored_after_startup_and_map_change(self):
        self.p._ignoreTill = self.now + 120
        self.pings = {'1': 800}
        self.p.check()
        self.assertFalse(self.joe.isvar(self.p, 'highping'))
        self.p._ignoreTill = 0
        self.p.onGameExit(None)
        self.assertEqual(self.now + 120, self.p._ignoreTill)

    def test_disabled_plugin_does_nothing(self):
        self.p.disable()
        self.pings = {'1': 800}
        self.p.check()
        self.assertFalse(self.joe.isvar(self.p, 'highping'))

    def test_cmd_ci_kicks_an_interrupted_player(self):
        self.pings = {'1': 999}
        self.mod.says('!ci joe')
        self.assertIsNone(self.console.clients.getByCID('1'))  # kicked

    def test_cmd_ci_leaves_a_normal_player(self):
        self.pings = {'1': 50}
        self.mod.clearMessageHistory()
        self.mod.says('!ci joe')
        self.assertIsNotNone(self.console.clients.getByCID('1'))
        self.assertEqual(['Joe is not CI'], self.mod.message_history)

    def test_cmd_ci_needs_a_name(self):
        self.mod.clearMessageHistory()
        self.mod.says('!ci')
        self.assertEqual(['Missing data, try !help ci'], self.mod.message_history)
