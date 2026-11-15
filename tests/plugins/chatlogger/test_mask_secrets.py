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

from unittest.mock import Mock
from b3.plugins.chatlogger import ChatData, CmdData, PrivateChatData, mask_secrets


class Test_mask_secrets(unittest.TestCase):

    def test_masked(self):
        self.assertEqual('!login ******', mask_secrets('!login s3cr3t'))
        self.assertEqual('!LOGIN ******', mask_secrets('!LOGIN my s3cr3t'))
        self.assertEqual('&login ******', mask_secrets('&login s3cr3t'))
        self.assertEqual('/login ******', mask_secrets('/login s3cr3t'))
        self.assertEqual('!setpassword ******', mask_secrets('!setpassword s3cr3t'))
        self.assertEqual('!setpassword ****** joe', mask_secrets('!setpassword s3cr3t joe'))

    def test_not_masked(self):
        for msg in ('hello', '!login', '!kick joe', '!loginfoo bar', 'please !login s3cr3t', '', None):
            self.assertEqual(msg, mask_secrets(msg))


class Test_database_data(unittest.TestCase):

    def setUp(self):
        self.plugin = Mock()
        self.plugin._save2db = True
        self.plugin._save2file = False
        self.plugin.console.time.return_value = 1234

    def make_event(self, data, target=None):
        event = Mock()
        event.client.id = 1
        event.client.name = 'Joe'
        event.client.team = 2
        event.data = data
        event.target = target
        return event

    def saved_data(self, obj):
        obj._save2db = Mock()
        obj.save()
        self.assertTrue(obj._save2db.called)
        return obj._save2db.call_args[0][0]

    def test_cmdlog_login(self):
        command = Mock()
        command.command = 'login'
        data = self.saved_data(CmdData(self.plugin, self.make_event((command, 's3cr3t', None))))
        self.assertEqual('******', data['data'])
        self.assertEqual('login', data['command'])

    def test_cmdlog_setpassword(self):
        command = Mock()
        command.command = 'setpassword'
        data = self.saved_data(CmdData(self.plugin, self.make_event((command, 's3cr3t joe', None))))
        self.assertEqual('****** joe', data['data'])

    def test_cmdlog_other_command(self):
        command = Mock()
        command.command = 'kick'
        data = self.saved_data(CmdData(self.plugin, self.make_event((command, 'joe s3cr3t', None))))
        self.assertEqual('joe s3cr3t', data['data'])

    def test_chatlog_login(self):
        data = self.saved_data(ChatData(self.plugin, self.make_event('!login s3cr3t')))
        self.assertEqual('!login ******', data['msg'])

    def test_chatlog_private_login(self):
        target = Mock()
        target.id = 2
        target.name = 'B3'
        target.team = 2
        data = self.saved_data(PrivateChatData(self.plugin, self.make_event('!login s3cr3t', target)))
        self.assertEqual('!login ******', data['msg'])
        self.assertEqual('PM', data['type'])
