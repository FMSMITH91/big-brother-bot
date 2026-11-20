# -*- coding: utf-8 -*-
"""
Plugin configuration reload without a restart (linuxgsm-panel request 4): SIGHUP, !reconfig and the control socket's
reload_plugins re-read and apply each plugin's file; a broken file keeps the previous configuration.
"""
import os
import shutil
import signal
import tempfile
import unittest
from unittest.mock import Mock

import b3
from b3.config import CfgConfigParser
from b3.plugin import Plugin
from tests import B3TestCase


class GreetPlugin(Plugin):
    requiresConfigFile = True

    def onLoadConfig(self):
        self.greeting = self.config.get('settings', 'greeting')


class Test_reloadPluginConfigs(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = os.path.join(self.dir, 'plugin_greet.ini')
        self.write('[settings]\ngreeting: hello\n')
        config = CfgConfigParser()
        config.load(self.path)
        self.plugin = GreetPlugin(self.console, config)
        self.plugin.onLoadConfig()
        self.console._plugins = {'greet': self.plugin}
        self.console.eventFeed = Mock()

    def write(self, text):
        with open(self.path, 'w') as f:
            f.write(text)

    def test_new_values_are_applied(self):
        self.write('[settings]\ngreeting: welcome\n')
        report = self.console.reloadPluginConfigs()
        self.assertEqual({'reloaded': ['greet'], 'failed': {}}, report)
        self.assertEqual('welcome', self.plugin.greeting)
        self.console.eventFeed.record.assert_called_once_with('config_reload', reloaded=['greet'], failed={})

    def test_broken_file_keeps_the_previous_configuration(self):
        self.write('[settings]\nno greeting here\n')
        report = self.console.reloadPluginConfigs()
        self.assertEqual([], report['reloaded'])
        self.assertIn('greet', report['failed'])
        self.assertEqual('hello', self.plugin.greeting)
        self.assertEqual('hello', self.plugin.config.get('settings', 'greeting'))

    def test_deleted_file_keeps_the_previous_configuration(self):
        os.unlink(self.path)
        report = self.console.reloadPluginConfigs()
        self.assertIn('greet', report['failed'])
        self.assertEqual('hello', self.plugin.greeting)

    def test_reconfig_applies_values(self):
        # !reconfig used to re-read the files without calling onLoadConfig
        self.console.config = Mock()
        self.console.updateDocumentation = Mock()
        self.write('[settings]\ngreeting: hi again\n')
        self.console.reloadConfigs()
        self.assertEqual('hi again', self.plugin.greeting)


class Test_sighup(unittest.TestCase):

    def test_handler_only_sets_a_flag(self):
        console = Mock()
        b3.hup_signal_handler(console)(getattr(signal, 'SIGHUP', 1), None)
        console.requestReload.assert_called_once_with()
        self.assertFalse(console.reloadPluginConfigs.called)  # the main loop does the work, not the signal handler

    def test_request_reload_sets_the_flag(self):
        from b3.parser import Parser
        parser = Parser.__new__(Parser)
        parser.requestReload()
        self.assertTrue(parser._reloadRequested)
