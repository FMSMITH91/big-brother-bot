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

from unittest.mock import Mock
from mockito import when
from b3.plugins.scheduler import DaylyTask, HourlyTask
from tests.plugins.scheduler import SchedulerTestCase


class Test_frostbite_tasks(SchedulerTestCase):

    def setUp(self):
        SchedulerTestCase.setUp(self)
        when(self.console).isFrostbiteGame().thenReturn(True)
        when(self.console).getPlugin('tk').thenReturn(Mock(name='tk'))

    def test_task_without_frostbite_command(self):
        # GIVEN a task having only a disable_plugin command on a frostbite game
        self.load_plugin("""<configuration plugin="scheduler">
            <hourly name="no rcon">
                <disable_plugin plugin="tk" />
            </hourly>
        </configuration>""")
        # THEN the task is loaded
        self.assertEqual(1, len(self.p._tasks))
        self.assertIsInstance(self.p._tasks[0], HourlyTask)

    def test_task_with_many_frostbite_commands(self):
        self.load_plugin("""<configuration plugin="scheduler">
            <hourly name="2 commands">
                <frostbite command="admin.say"><arg>hello</arg><arg>all</arg></frostbite>
                <frostbite command="punkBuster.pb_sv_command"><arg>pb_sv_update</arg></frostbite>
            </hourly>
        </configuration>""")
        self.assertEqual(1, len(self.p._tasks))
        self.assertEqual(2, self.p._tasks[0]._init_rcon_commands())

    def test_second_frostbite_command_without_command_attribute(self):
        # every frostbite element must be validated, not only the 1st one
        self.load_plugin("""<configuration plugin="scheduler">
            <hourly name="bad">
                <frostbite command="admin.say"><arg>hello</arg><arg>all</arg></frostbite>
                <frostbite><arg>pb_sv_update</arg></frostbite>
            </hourly>
        </configuration>""")
        self.assertEqual(0, len(self.p._tasks))


class Test_daily_task(SchedulerTestCase):

    def test_daily_task_without_hour(self):
        # GIVEN
        self.load_plugin("""<configuration plugin="scheduler">
            <daily name="midnight">
                <rcon>say hello</rcon>
            </daily>
        </configuration>""")
        # THEN
        self.assertEqual(1, len(self.p._tasks))
        task = self.p._tasks[0]
        self.assertIsInstance(task, DaylyTask)
        self.assertIsNotNone(task.cronTab)

    def test_daily_task_with_hour(self):
        self.load_plugin("""<configuration plugin="scheduler">
            <daily name="3am" hour="3" minutes="30">
                <rcon>say hello</rcon>
            </daily>
        </configuration>""")
        self.assertEqual(1, len(self.p._tasks))

    def test_convertCronHourToUTC_int(self):
        self.p = self.load_plugin("""<configuration plugin="scheduler"/>""")
        self.p._tzOffset = 2
        self.assertEqual(22, self.p._convertCronHourToUTC(0))
        self.assertEqual(22, self.p._convertCronHourToUTC('0'))
        self.assertEqual('*', self.p._convertCronHourToUTC('*'))
        self.assertEqual('1/4', self.p._convertCronHourToUTC('3/4'))
