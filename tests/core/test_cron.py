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

import threading
import time
import unittest
from unittest.mock import sentinel, Mock
from b3.cron import CronTab, OneTimeCronTab, PluginCronTab, Cron
from tests import B3TestCase

class Test_Crontab(unittest.TestCase):

    def test_constructor_defaults(self):
        command = sentinel
        tab = CronTab(command)
        self.assertEqual(command, tab.command)
        self.assertEqual(0, tab.second)
        self.assertEqual(-1, tab.minute)
        self.assertEqual(-1, tab.hour)
        self.assertEqual(-1, tab.day)
        self.assertEqual(-1, tab.month)
        self.assertEqual(-1, tab.dow)
        self.assertEqual(0, tab.maxRuns)

    def test_constructor(self):
        command = sentinel
        tab = CronTab(command, second=1, minute=2, hour=3, day=4, month=5, dow=1)
        self.assertEqual(command, tab.command)
        self.assertEqual(1, tab.second)
        self.assertEqual(2, tab.minute)
        self.assertEqual(3, tab.hour)
        self.assertEqual(4, tab.day)
        self.assertEqual(5, tab.month)
        self.assertEqual(1, tab.dow)

    def test_dow(self):
        tab = CronTab(None)

        tab.dow = '*' # any day
        self.assertEqual(-1, tab.dow)

        tab.dow = 0 # sunday
        self.assertEqual(0, tab.dow)

        tab.dow = 1 # monday
        self.assertEqual(1, tab.dow)

        tab.dow = 2 # tuesday
        self.assertEqual(2, tab.dow)

        tab.dow = 3 # wednesday
        self.assertEqual(3, tab.dow)

        tab.dow = 4 # thursday
        self.assertEqual(4, tab.dow)

        tab.dow = 5 # friday
        self.assertEqual(5, tab.dow)

        tab.dow = 6 # saturday
        self.assertEqual(6, tab.dow)

        try:
            tab.dow = 7
        except ValueError:
            pass
        else:
            self.fail("expecting ValueError when setting dow to 7")

        try:
            tab.dow = -1
        except ValueError:
            pass
        else:
            self.fail("expecting ValueError when setting dow to 7")

    def test_run(self):
        command = Mock(name="command")
        tab = CronTab(command)
        assert not command.called
        tab.run()
        assert command.called


    def test_match(self):
        tab = CronTab(None, second='*', minute='*', hour='*', day='*', month='*', dow='*')
        self.assertTrue(tab.match(time.gmtime()))

        tab = CronTab(None, second='*', minute='*', hour='*', day='*', month='*', dow='0,1,2,3,4,5,6')
        self.assertTrue(tab.match(time.gmtime()))


class Test_OneTimeCrontab(unittest.TestCase):

    def test_constructor(self):
        tab = OneTimeCronTab(None)
        self.assertEqual(1, tab.maxRuns)


class Test_PluginCronTab(unittest.TestCase):

    def test(self):
        CronTab.match = Mock(return_value=True)
        mock_command = Mock()
        p = Mock()
        tab = PluginCronTab(plugin=p, command=mock_command)

        mock_command.reset_mock()
        p.isEnabled = Mock(return_value=True)
        self.assertTrue(tab.match(time.gmtime()))
        tab.run()
        self.assertTrue(mock_command.called)

        mock_command.reset_mock()
        p.isEnabled = Mock(return_value=False)
        self.assertFalse(tab.match(time.gmtime()))
        tab.run()
        self.assertFalse(mock_command.called)


class Test_Crontab_getRate(unittest.TestCase):

    def setUp(self):
        self._t = CronTab(None)

    def tearDown(self):
        pass

    def t(self, param):
        return self._t._getRate(param, 60)

    def test_None(self):
        self.assertRaises(TypeError, self.t, None)

    def test_getRate_int(self):
        self.assertEqual(0, self.t(0))
        self.assertEqual(1, self.t(1))
        self.assertEqual(59, self.t(59))
        self.assertRaises(ValueError, self.t, 60)
        self.assertRaises(ValueError, self.t, -1)

    def test_float(self):
        self.assertEqual(0, self.t(0.0))
        self.assertEqual(1, self.t(1.0))
        self.assertEqual(59, self.t(59.0))
        self.assertRaises(ValueError, self.t, 60.0)
        self.assertRaises(ValueError, self.t, -1.0)

    def test_str_every(self):
        self.assertEqual(-1, self.t('*'))

    def test_str_everySo(self):
        self.assertEqual(list(range(0,60,2)), self.t('*/2') )
        self.assertEqual(list(range(0,60,17)), self.t('*/17'))
        self.assertEqual([0,59], self.t('*/59'))
        self.assertEqual([0], self.t('*/60'))
        self.assertRaises(ValueError, self.t, ('*/61'))
        self.assertRaises(TypeError, self.t, ('*/-1'))
        self.assertRaises(ValueError, self.t, ('*/80'))

    def test_str_range(self):
        self.assertEqual(list(range(5,12)), self.t('5-11'))
        self.assertRaises(TypeError, self.t, ('-5-11'))
        self.assertRaises(ValueError, self.t, ('35-11'))
        self.assertRaises(TypeError, self.t, ('5--11'))
        self.assertRaises(ValueError, self.t, ('5-80'))

    def test_str_range_with_step(self):
        self.assertEqual(list(range(5,12,2)), self.t('5-11/2'))
        self.assertEqual([5], self.t('5-11/60'))
        self.assertRaises(ValueError, self.t, ('5-11/80'))
        self.assertRaises(TypeError, self.t, ('5-11/'))
        self.assertRaises(TypeError, self.t, ('5-11/-1'))

    def test_str_other(self):
        self.assertRaises(TypeError, self.t, (''))
        self.assertRaises(TypeError, self.t, ('test'))

    def test_list(self):
        self.assertEqual([5,11,32,45], self.t('5,11,45,32'))
        self.assertEqual([0,1,2,5,6,7,8], self.t('5-8,0-2'))
        self.assertEqual([5,6,7,20,30], self.t('5-7, 20, 30'))
        self.assertEqual([5,6,7,30,40], self.t('5-7,40,30'))
        self.assertEqual([0,5,6,7,40], self.t('5-7,40,0'))
        self.assertEqual([5,7,9,11,30,40,41,42], self.t('5-12/2, 30, 40-42'))
        self.assertRaises(TypeError, self.t, ('5-12/2, -5, 40-42'))


class Test_Cron(B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        self.cron = Cron(self.console)
        #self.console.verbose = lambda *args: sys.stdout.write(str(args) + "\n")

    def test_add(self):
        mock_tab = Mock(spec=CronTab)
        res = self.cron.add(mock_tab)
        self.assertEqual(1, len(self.cron._tabs))
        self.assertEqual(id(mock_tab), res)
        self.assertIn(id(mock_tab), self.cron._tabs)

    def test_add_operator(self):
        mock_tab = Mock(spec=CronTab)
        self.cron + mock_tab
        self.assertEqual(1, len(self.cron._tabs))
        self.assertIn(id(mock_tab), self.cron._tabs)

    def test_cancel(self):
        mock_tab = Mock(spec=CronTab)
        res = self.cron.add(mock_tab)
        self.assertEqual(1, len(self.cron._tabs))

        self.cron.cancel(-1)
        self.assertEqual(1, len(self.cron._tabs))

        self.cron.cancel(id(mock_tab))
        self.assertNotIn(id(mock_tab), self.cron._tabs)
        self.assertEqual(0, len(self.cron._tabs))

    def test_sub_operator(self):
        mock_tab = Mock(spec=CronTab)
        res = self.cron.add(mock_tab)
        self.assertEqual(1, len(self.cron._tabs))
        self.cron - mock_tab
        self.assertNotIn(res, self.cron._tabs)
        self.assertEqual(0, len(self.cron._tabs))

    def test_create(self):
        crontab_id = self.cron.create(None)
        self.assertEqual(1, len(self.cron._tabs))
        self.assertIn(crontab_id, self.cron._tabs)
        self.assertEqual(CronTab, type(self.cron._tabs[crontab_id]))


class Test_Crontab_ranges(unittest.TestCase):
    """
    Day of month is 1-31 and month is 1-12 (as returned by time.gmtime), range upper bounds are inclusive.
    """

    @staticmethod
    def gmtime(*args):
        import calendar
        return time.gmtime(calendar.timegm(args + (0,) * (6 - len(args))))

    def test_last_day_and_month(self):
        tab = CronTab(None, second=0, minute=0, hour=0, day='31', month='12')
        self.assertEqual(31, tab.day)
        self.assertEqual(12, tab.month)
        self.assertTrue(tab.match(self.gmtime(2026, 12, 31)))
        tab = CronTab(None, second=0, minute=0, hour=0, day=31, month=12)
        self.assertTrue(tab.match(self.gmtime(2026, 12, 31)))

    def test_day_and_month_zero_rejected(self):
        self.assertRaises(ValueError, CronTab, None, day='0')
        self.assertRaises(ValueError, CronTab, None, day=0)
        self.assertRaises(ValueError, CronTab, None, month='0')
        self.assertRaises(ValueError, CronTab, None, month='0-5')
        self.assertRaises(ValueError, CronTab, None, day='32')
        self.assertRaises(ValueError, CronTab, None, month='13')

    def test_every_n_months_and_days(self):
        self.assertEqual([1, 7], CronTab(None, month='*/6').month)
        self.assertEqual([1, 4, 7, 10], CronTab(None, month='*/3').month)
        self.assertEqual([1, 11, 21, 31], CronTab(None, day='*/10').day)
        self.assertEqual(list(range(0, 60, 15)), CronTab(None, minute='*/15').minute)

    def test_range_upper_bound(self):
        self.assertRaises(ValueError, CronTab, None, minute='50-60')
        self.assertRaises(ValueError, CronTab, None, hour='20-24')
        self.assertEqual(list(range(50, 60)), CronTab(None, minute='50-59').minute)
        self.assertEqual([28, 29, 30, 31], CronTab(None, day='28-31').day)
        self.assertEqual([10, 11, 12], CronTab(None, month='10-12').month)


class _FastEvent(threading.Event):
    """
    A stop event whose wait() returns immediately: makes the cron loop run without real time delays.
    """
    def wait(self, timeout=None):
        return self.is_set()


class Test_Cron_SystemExit(unittest.TestCase):
    """
    A SystemExit raised by a crontab (i.e: Parser.critical) used to silently kill the cron thread.
    """

    def setUp(self):
        self.console = Mock()
        self.cron = Cron(self.console)
        self.cron._stopEvent = _FastEvent()
        self.exit_runs = 0
        self.counter_runs = 0

    def counter(self):
        self.counter_runs += 1
        if self.counter_runs >= 3:
            self.cron.stop()

    def test_cron_survives_systemexit_while_b3_running(self):
        def exiting():
            self.exit_runs += 1
            raise SystemExit(220)
        self.cron.create(exiting, second='*')
        self.cron.create(self.counter, second='*')
        self.cron.run()  # must not propagate SystemExit
        self.assertEqual(3, self.exit_runs)
        self.assertEqual(3, self.counter_runs)
        self.assertTrue(self.console.error.called)

    def test_cron_ends_on_systemexit_during_shutdown(self):
        def exiting():
            # what Parser.critical does: shutdown() stops the cron, then SystemExit is raised
            self.exit_runs += 1
            self.cron.stop()
            raise SystemExit(220)
        self.cron.create(exiting, second='*')
        self.cron.create(self.counter, second='*')
        self.cron.run()  # must not propagate SystemExit
        self.assertEqual(1, self.exit_runs)
        self.assertEqual(0, self.counter_runs)



class Test_Cron_stop_waits_for_running_crontab(unittest.TestCase):
    """
    B3 closes the database right after stopping the cron: a crontab still running (i.e: a database query) used to
    fail with 'read of closed file'.
    """

    def test_stop_waits(self):
        cron = Cron(Mock())
        cron._stopEvent = _FastEvent()
        started = threading.Event()
        finished = []

        def slow_job():
            started.set()
            threading.Event().wait(0.3)
            finished.append(True)

        cron.create(slow_job, second='*')
        thread = threading.Thread(target=cron.run, daemon=True)
        thread.start()
        self.assertTrue(started.wait(5))
        cron.stop()
        self.assertListEqual([True], finished)
        thread.join(5)
        self.assertFalse(thread.is_alive())

if __name__ == '__main__':
    unittest.main()
