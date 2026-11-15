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
import threading
import sys

from b3.config import CfgConfigParser
from b3.config import MainConfig
from contextlib import contextmanager

logging.raiseExceptions = False  # get rid of 'No handlers could be found for logger output' message
import b3.output # do not remove, needed because the module alters some defaults of the logging module
log = logging.getLogger('output')
log.setLevel(logging.WARNING)

from unittest.mock import Mock, patch
import time
import unittest
from b3.events import Event


import mockito as _mockito

if not getattr(_mockito.when, '_b3_lenient', False):
    # The B3 test suite was written against old mockito releases where `when(obj)` was lenient: calling a method with
    # arguments that were not stubbed simply returned None. mockito >= 1.0 is strict by default and raises instead.
    # Restore the old default (tests can still opt in with strict=True). This module is imported before any test
    # module, so their `from mockito import when` picks up this wrapper.
    _mockito_when = _mockito.when

    def _lenient_when(obj, strict=False):
        return _mockito_when(obj, strict=strict)

    _lenient_when._b3_lenient = True
    _mockito.when = _lenient_when


if not hasattr(unittest.TestCase, 'assertDictContainsSubset'):
    # removed from unittest in Python 3.12; many B3 tests still rely on it
    def _assertDictContainsSubset(self, subset, dictionary, msg=None):
        missing = [k for k in subset if k not in dictionary]
        mismatched = ['%r: expected %r, actual %r' % (k, subset[k], dictionary[k])
                      for k in subset if k in dictionary and dictionary[k] != subset[k]]
        if missing or mismatched:
            parts = []
            if missing:
                parts.append('Missing: %s' % ','.join(repr(m) for m in missing))
            if mismatched:
                parts.append('Mismatched values: %s' % ', '.join(mismatched))
            self.fail(self._formatMessage(msg, '; '.join(parts)))
    unittest.TestCase.assertDictContainsSubset = _assertDictContainsSubset


testcase_lock = threading.Lock()  # together with flush_console_streams, helps getting logging output related to the
# correct test in test runners such as the one in PyCharm IDE.


class logging_disabled(object):
    """
    context manager that temporarily disable logging.

    USAGE:
        with logging_disabled():
            # do stuff
    """
    DISABLED = False

    def __init__(self):
        self.nested = logging_disabled.DISABLED

    def __enter__(self):
        if not self.nested:
            logging.getLogger('output').propagate = False
            logging_disabled.DISABLED = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.nested:
            logging.getLogger('output').propagate = True
            logging_disabled.DISABLED = False


def flush_console_streams():
    sys.stderr.flush()
    sys.stdout.flush()


class B3TestCase(unittest.TestCase):

    def setUp(self):
        testcase_lock.acquire()
        # release through addCleanup: cleanups run even when setUp fails (tearDown does not), so a single broken
        # setUp can no longer leave the lock held and deadlock every following test
        self.addCleanup(testcase_lock.release)
        flush_console_streams()

        # create a FakeConsole parser
        self.parser_conf = MainConfig(CfgConfigParser(allow_no_value=True))
        self.parser_conf.loadFromString(r"""""")
        with logging_disabled():
            from b3.fake import FakeConsole
            self.console = FakeConsole(self.parser_conf)

        self.console.screen = Mock()
        self.console.time = time.time
        self.console.upTime = Mock(return_value=3)

        self.console.cron.stop()

        def myError(msg, *args, **kwargs):
            print((("ERROR: %s" % msg) % args))
        self.console.error = myError

    def tearDown(self):
        flush_console_streams()

    @contextmanager
    def assertRaiseEvent(self, event_type, event_client=None, event_data=None, event_target=None):
        """
        USAGE:
            def test_team_change(self):
            # GIVEN
            self.client._team = TEAM_RED
            # THEN
            with self.assertRaiseEvent(
                event_type='EVT_CLIENT_TEAM_CHANGE',
                event_data=24,
                event_client=self.client,
                event_target=None):
                # WHEN
                self.client.team = 24
        """
        event_type_name = self.console.getEventName(event_type)
        self.assertIsNotNone(event_type_name, "could not find event with name '%s'" % event_type)

        with patch.object(self.console, 'queueEvent') as queueEvent:
            yield
            if event_type is None:
                assert not queueEvent.called
                return
            assert queueEvent.called, "No event was fired"

        def assertEvent(queueEvent_call_args):
            eventraised = queueEvent_call_args[0][0]
            return type(eventraised) == Event \
                and self.console.getEventName(eventraised.type) == event_type_name \
                and eventraised.data == event_data \
                and eventraised.target == event_target \
                and eventraised.client == event_client

        if not any(map(assertEvent, queueEvent.call_args_list)):
            raise AssertionError("Event %s(%r) not fired" % (self.console.getEventName(event_type), {
                'event_client': event_client,
                'event_data': event_data,
                'event_target': event_target
            }))


## Makes a way to patch threading.Timer so it behave synchronously and instantly
## Usage:
##
## @patch('threading.Timer', new_callable=lambda: InstantTimer)
## def test_my_code_using_threading_Timer(instant_timer):
##     t = threading.Timer(30, print, args=['hi'])
##     t.start()  # prints 'hi' instantly and in the same thread
##
class InstantTimer(object):
    def __init__(self, interval, function, args=[], kwargs={}):
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def cancel(self):
        pass

    def start(self):
        self.run()

    def run(self):
        self.function(*self.args, **self.kwargs)
