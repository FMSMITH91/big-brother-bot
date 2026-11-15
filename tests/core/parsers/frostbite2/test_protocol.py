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

import sys
import threading
import unittest

from unittest.mock import Mock
from b3.parsers.frostbite2 import protocol
from b3.parsers.frostbite2.protocol import FrostbiteServer


class Test_client_sequence_numbers(unittest.TestCase):

    def test_sequence_numbers_are_unique_across_threads(self):
        seen = []
        lock = threading.Lock()

        def worker():
            local = []
            for _ in range(5000):
                packet = protocol.EncodeClientRequest(('admin.say', 'hello', 'all'))
                local.append(protocol.DecodePacket(packet)[2])
            with lock:
                seen.extend(local)

        old_interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        try:
            threads = [threading.Thread(target=worker) for _ in range(4)]
            [t.start() for t in threads]
            [t.join() for t in threads]
        finally:
            sys.setswitchinterval(old_interval)
        self.assertEqual(len(seen), len(set(seen)))


class Test_FrostbiteServer_command(unittest.TestCase):

    def setUp(self):
        # build a FrostbiteServer without its thread and network connection
        self.server = FrostbiteServer.__new__(FrostbiteServer)
        threading.Thread.__init__(self.server)
        self.server._stopEvent = threading.Event()
        self.server.command_timeout = 0.3
        self.server.pending_commands = {}
        self.server._FrostbiteServer__command_reply_event = threading.Event()
        self.server.observers = set()
        self.server.frostbite_dispatcher = Mock()
        self.server.frostbite_dispatcher.connected = True

    def test_response_received_before_send_command_returns(self):
        # GIVEN a game server so fast that the response is handled (by the asyncore thread) before send_command()
        # returns to the thread which sent the command
        def send_command(*command, **kwargs):
            command_id = 42
            before_send = kwargs.get('before_send')
            if before_send:
                before_send(command_id)
            self.server._on_command_response(command_id, ['OK', 'BF4', '1234'])
            return command_id
        self.server.frostbite_dispatcher.send_command = Mock(side_effect=send_command)
        # WHEN
        rv = self.server.command('version')
        # THEN
        self.assertListEqual(['BF4', '1234'], rv)
        self.assertDictEqual({}, self.server.pending_commands)


class Test_ThreadSafeDispatcherWithSend(unittest.TestCase):

    def test_concurrent_send_and_initiate_send(self):
        import asyncore
        from unittest.mock import patch
        sent = []

        def fake_socket_send(dispatcher, data):
            # partial writes, like a real non blocking socket under load
            n = max(1, len(data) // 2) if data else 0
            sent.append(bytes(data[:n]))
            return n

        dispatcher = protocol.ThreadSafeDispatcherWithSend()
        expected = b''.join(b'packet%05d;' % i for i in range(3000))
        stop = threading.Event()

        def writer():
            for i in range(3000):
                dispatcher.send(b'packet%05d;' % i)
            stop.set()

        def loop():
            while not stop.is_set():
                dispatcher.handle_write()

        old_interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        try:
            with patch.object(asyncore.dispatcher, 'send', fake_socket_send):
                threads = [threading.Thread(target=writer), threading.Thread(target=loop)]
                [t.start() for t in threads]
                [t.join() for t in threads]
                while dispatcher.out_buffer:
                    dispatcher.handle_write()
        finally:
            sys.setswitchinterval(old_interval)
        self.assertEqual(expected, b''.join(sent))
