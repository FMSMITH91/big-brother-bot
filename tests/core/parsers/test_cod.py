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

import logging
from unittest.mock import Mock
from unittest.mock import patch
from mockito import mock, when, any as anything
import unittest
from b3.config import XmlConfigParser
from b3.parsers.cod import CodParser

log = logging.getLogger("test")
log.setLevel(logging.INFO)


class CodTestCase(unittest.TestCase):
    """
    Test case that is suitable for testing Cod parser specific features
    """

    @classmethod
    def setUpClass(cls):
        from b3.parsers.q3a.abstractParser import AbstractParser
        from b3.fake import FakeConsole
        AbstractParser.__bases__ = (FakeConsole,)
        # Now parser inheritance hierarchy is :
        # CodParser -> AbstractParser -> FakeConsole -> Parser

        logging.getLogger('output').setLevel(logging.ERROR)

    def setUp(self):
        self.parser_conf = XmlConfigParser()
        self.parser_conf.loadFromString("""<configuration>
                <settings name="server">
                    <set name="game_log"/>
                </settings>
            </configuration>""")
        self.console = CodParser(self.parser_conf)

        self.output_mock = mock()
        # simulate game server actions
        def write(*args, **kwargs):
            pretty_args = list(map(repr, args)) + ["%s=%s" % (k, v) for k, v in kwargs.items()]
            log.info("write(%s)" % ', '.join(pretty_args))
            return self.output_mock.write(*args, **kwargs)
        self.console.write = Mock(wraps=write)

        self.player = self.console.clients.newClient(cid="4", guid="theGuid", name="theName", ip="11.22.33.44")


    def tearDown(self):
        if hasattr(self, "parser"):
            del self.parser.clients
            self.parser.working = False




class Test_parser_API(CodTestCase):

    def test_getPlayerList_without_punkbuster(self):
        # GIVEN
        self.console.PunkBuster = None
        when(self.console).write('status', maxRetries=anything()).thenReturn('''\
map: mp_villa
num score ping guid   name            lastmsg address               qport rate
--- ----- ---- ---------- --------------- ------- --------------------- ------ -----
  0     0    0      0 democlient^7         1650 unknown                 1773  5000
  1     0   55 63281996 BandAid^7              50 11.11.11.11:524        8045 25000
  2     0  157 81554346 hugobongenhielm^7      50 11.11.11.11:524    22481 25000
  3     0  156 86330555 Irish^7                 0 11.11.11.11:9162     14288 25000
  4     0  999 68003079 Ashhole^7             750 11.11.11.11:19978 19033 25000
  5     5   53 318670 bigredtwit^7            011.11.11.11:28966     1259 25000
''')
        # WHEN
        rv = self.console.getPlayerList()
        # THEN
        self.assertDictContainsSubset({
            'slot': '1', 'score': '0', 'ping': '55', 'guid': '63281996', 'name': 'BandAid^7', 'last': '50', 'ip': '11.11.11.11', 'pbid': None
        }, rv.get('1', {}), rv)
        self.assertDictContainsSubset({
            'slot': '2', 'score': '0', 'ping': '157', 'guid': '81554346', 'name': 'hugobongenhielm^7', 'last': '50', 'ip': '11.11.11.11', 'pbid': None
        }, rv.get('2', {}), rv)
        self.assertDictContainsSubset({
            'slot': '3', 'score': '0', 'ping': '156', 'guid': '86330555', 'name': 'Irish^7', 'last': '0', 'ip': '11.11.11.11', 'pbid': None
        }, rv.get('3', {}), rv)
        self.assertDictContainsSubset({
            'slot': '4', 'score': '0', 'ping': '999', 'guid': '68003079', 'name': 'Ashhole^7', 'last': '750', 'ip': '11.11.11.11', 'pbid': None
        }, rv.get('4', {}), rv)
        self.assertDictContainsSubset({
            'slot': '5', 'score': '5', 'ping': '53', 'guid': '318670', 'name': 'bigredtwit^7', 'last': '0', 'ip': '11.11.11.11', 'pbid': None
        }, rv.get('5', {}), rv)


STATUS_WITH_JOE = '''\
map: mp_harbor
num score ping guid   name            lastmsg address               qport rate
--- ----- ---- ---------- --------------- ------- --------------------- ------ -----
  7     0   48 2019598 Joe^7                  0 11.22.33.55:28960      1773  5000
'''


class Test_players_connected_before_b3(CodTestCase):
    """
    Live CoD1 test (2026-11-15): a player who was on the server when B3 started typed !iamgod and B3 only used the
    line to start authenticating him: the command itself was dropped.
    """

    def setUp(self):
        CodTestCase.setUp(self)
        self.console.PunkBuster = None
        when(self.console).write('status', maxRetries=anything()).thenReturn(STATUS_WITH_JOE)
        when(self.console).write('status').thenReturn(STATUS_WITH_JOE)
        self.queued = []
        self.console.queueEvent = lambda event, expire=10: self.queued.append(event)
        self.timers = []
        patcher = patch('b3.parsers.cod.Timer', side_effect=self._timer)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.console._counter.clear)

    def _timer(self, interval, function, args=()):
        timer = Mock()
        timer.start = lambda: self.timers.append((function, args))
        return timer

    def run_timers(self):
        while self.timers:
            function, args = self.timers.pop(0)
            function(*args)

    def events(self, key):
        event_id = self.console.getEventID(key)
        return [e for e in self.queued if e.type == event_id]

    def test_command_from_unauthenticated_player_is_handled_once_authenticated(self):
        # WHEN Joe, unknown to B3, types a command
        self.console.parseLine('1319:34 say;2019598;7;Joe;!iamgod')
        # THEN nothing happens until he is authenticated...
        self.assertEqual([], self.events('EVT_CLIENT_SAY'))
        self.run_timers()
        # ...and then his command is handled, after his join
        joins = self.events('EVT_CLIENT_JOIN')
        says = self.events('EVT_CLIENT_SAY')
        self.assertEqual(1, len(joins))
        self.assertEqual(['!iamgod'], [e.data for e in says])
        self.assertIs(joins[0].client, says[0].client)
        self.assertLess(self.queued.index(joins[0]), self.queued.index(says[0]))

    def test_kept_lines_are_dropped_when_the_player_leaves(self):
        self.console.parseLine('1319:34 say;2019598;7;Joe;!iamgod')
        self.console.parseLine('1319:35 Q;2019598;7;Joe')
        self.run_timers()
        self.assertEqual([], self.events('EVT_CLIENT_SAY'))

    def test_players_already_connected_are_authenticated_at_startup(self):
        # WHEN B3 has started its plugins
        self.console.joinConnectedPlayers()
        # THEN the players listed by rcon status are authenticated without waiting for them to do something
        joe = self.console.clients.getByCID('7')
        self.assertIsNotNone(joe)
        self.assertEqual('2019598', joe.guid)
        self.assertEqual(1, len(self.events('EVT_CLIENT_JOIN')))
        # and a known player is not authenticated twice
        self.queued[:] = []
        self.console.joinConnectedPlayers()
        self.assertEqual([], self.events('EVT_CLIENT_JOIN'))


# Builds a CoD parser on FakeConsole, makes it start authenticating an unknown player (which arms the real
# newPlayer timer), then lets the main thread end, as B3 does after "EXITING".
EXIT_WITH_PENDING_TIMER = '''
import sys
from b3.parsers.q3a.abstractParser import AbstractParser
from b3.fake import FakeConsole
AbstractParser.__bases__ = (FakeConsole,)
from b3.config import XmlConfigParser
from b3.parsers.cod import CodParser
conf = XmlConfigParser()
conf.loadFromString('<configuration><settings name="server"><set name="game_log"/></settings></configuration>')
console = CodParser(conf)
console.PunkBuster = None
console.write = lambda *args, **kwargs: ''
console.queueEvent = lambda *args, **kwargs: None
console.parseLine('1319:34 say;2019598;7;Joe;!iamgod')
assert console._counter, 'no authentication timer was armed'
console.working = False
print('ready', flush=True)
'''


class Test_pending_timers_do_not_block_shutdown(CodTestCase):
    """
    linuxgsm-panel add-ons (2026-11-18): B3 printed "EXITING: 0" but its process stayed alive, because the
    newPlayer / clients.sync threading.Timer threads were not daemon. In a container the stop then waited until
    the runtime killed B3 (exit 137).
    """

    def test_process_exits_at_once_with_an_authentication_timer_pending(self):
        import os
        import subprocess
        import sys
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        import tempfile
        stderr = tempfile.TemporaryFile(mode='w+')
        self.addCleanup(stderr.close)
        proc = subprocess.Popen([sys.executable, '-c', EXIT_WITH_PENDING_TIMER], cwd=root,
                                stdout=subprocess.PIPE, stderr=stderr, text=True)
        try:
            for line in proc.stdout:  # FakeConsole prints a line of its own first
                if line.strip() == 'ready':
                    break
            else:
                proc.wait()
                stderr.seek(0)
                self.fail('the script failed:\n' + stderr.read())
            # the timer fires after 2 s: a non-daemon timer keeps the process alive at least that long
            self.assertEqual(0, proc.wait(timeout=1.5))
        except subprocess.TimeoutExpired:
            self.fail('B3 did not exit while an authentication timer was pending')
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            proc.stdout.close()

    def test_parser_timers_are_daemon(self):
        import threading
        self.console.PunkBuster = None
        when(self.console).write('status', maxRetries=anything()).thenReturn('')
        when(self.console).write('status').thenReturn('')
        self.console.queueEvent = lambda event, expire=10: None
        self.addCleanup(self.console._counter.clear)
        before = set(threading.enumerate())
        self.console.parseLine('1319:34 say;2019598;7;Joe;!iamgod')
        self.console.OnExitlevel('ExitLevel', '')
        started = [t for t in threading.enumerate() if t not in before and isinstance(t, threading.Timer)]
        for timer in started:
            self.addCleanup(timer.cancel)
        self.assertEqual(2, len(started))
        self.assertTrue(all(t.daemon for t in started), started)

    def test_newPlayer_does_not_rearm_once_b3_is_stopping(self):
        self.console._counter['7'] = 1
        self.addCleanup(self.console._counter.clear)
        self.console.working = False
        self.addCleanup(setattr, self.console, 'working', True)
        with patch('b3.parsers.cod.Timer') as timer:
            self.assertIsNone(self.console.newPlayer('7', '2019598', 'Joe'))
        timer.assert_not_called()
