# -*- coding: utf-8 -*-
"""
Helpers for the CoD parser tests that follow a player through authentication: rcon status is mocked, the
authentication timers are run by hand and the queued events are kept.
"""

from unittest.mock import Mock
from unittest.mock import patch
from mockito import when, any as anything


class CodAuthMixin(object):

    def setUpAuthQueue(self, status):
        self.console.PunkBuster = None
        when(self.console).write('status', maxRetries=anything()).thenReturn(status)
        when(self.console).write('status').thenReturn(status)
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
