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

import binascii
import socket
import threading
import time
import unittest

from b3.parsers.battleye.protocol import BattleyeServer
from b3.parsers.battleye.protocol import CommandTimeoutError


def _be_packet(body):
    body = b'\xff' + body
    crc = binascii.crc32(body) & 0xffffffff
    return b'BE' + crc.to_bytes(4, 'little') + body


class FakeBattleyeUdpServer(object):
    """
    Minimal BattlEye rcon server listening on localhost.
    - 'slow' is answered after 0.6s
    - 'players' is answered with a 2 parts multi-packet response
    - other commands are answered with 'resp:<command>' after 0.8s
    """

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', 0))
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def reply_later(self, delay, data, addr):
        def reply():
            time.sleep(delay)
            if not self.stopped.is_set():
                self.sock.sendto(_be_packet(data), addr)
        threading.Thread(target=reply, daemon=True).start()

    def serve(self):
        while not self.stopped.is_set():
            try:
                d, a = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            tp = d[7]
            if tp == 0:
                self.sock.sendto(_be_packet(b'\x00\x01'), a)
            elif tp == 1:
                seq = d[8]
                cmd = d[9:].decode()
                if cmd == 'slow':
                    self.reply_later(0.6, bytes([1, seq]) + b'response-to-slow', a)
                elif cmd == 'players':
                    self.sock.sendto(_be_packet(bytes([1, seq, 0, 2, 0]) + b'part0-'), a)
                    self.sock.sendto(_be_packet(bytes([1, seq, 0, 2, 1]) + b'part1'), a)
                elif cmd:
                    self.reply_later(0.8, bytes([1, seq]) + ('resp:' + cmd).encode(), a)

    def stop(self):
        self.stopped.set()
        self.sock.close()


class Test_BattleyeServer_command_responses(unittest.TestCase):

    def setUp(self):
        self.fake_server = FakeBattleyeUdpServer()
        self.addCleanup(self.fake_server.stop)
        self.conn = BattleyeServer('127.0.0.1', self.fake_server.port, 'password')
        # cleanups also run when setUp fails, so threads are never leaked into later tests
        self.addCleanup(self.conn.stop)
        self.assertTrue(self.conn.connected)

    def test_multipacket_response(self):
        self.assertEqual('part0-part1', self.conn.command('players'))

    def test_late_response_is_not_given_to_next_command(self):
        # GIVEN a command that times out before its response arrives
        with self.assertRaises(CommandTimeoutError):
            self.conn.command('slow', timeout=0.3)
        # WHEN the next command is sent while the late response to the previous one is still to come
        rv = self.conn.command('version')
        # THEN the next command gets its own response, not the stale one
        self.assertEqual('resp:version', rv)
