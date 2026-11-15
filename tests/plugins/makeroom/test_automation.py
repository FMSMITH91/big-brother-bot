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

import time
import pytest
from textwrap import dedent
from tests.plugins.makeroom import *
from unittest.mock import call, Mock


@pytest.fixture
def plugin(console):
    p = plugin_maker_ini(console, dedent("""
        [commands]
        makeroomauto-mrauto: 20
        [automation]
        enabled: no
        total_slots: 3
        min_free_slots: 1
    """))
    p._delay = 0
    return p


def test_kick_last_connected_non_member_when_on(plugin, superadmin, joe, moderator):
    # GIVEN
    plugin._automation_enabled = True
    plugin._total_slots = 3
    plugin._min_free_slots = 1
    joe.kick = Mock()
    moderator.kick = Mock()
    # WHEN
    superadmin.connects(0)
    joe.connects(1)
    moderator.connects(2)
    # THEN
    assert [] == moderator.kick.mock_calls
    assert [call(admin=None, reason='to free a slot', silent=True, keyword='makeroom')] == joe.kick.mock_calls


def test_kick_non_member_when_on(plugin, superadmin, joe):
    # GIVEN
    plugin._automation_enabled = True
    plugin._total_slots = 2
    plugin._min_free_slots = 1
    joe.kick = Mock()
    # WHEN
    superadmin.connects(0)
    joe.connects(1)
    # THEN
    assert [call(reason='to free a slot', silent=True, keyword='makeroom')] == joe.kick.mock_calls


def test_kick_non_member_when_on_with_delay(plugin, superadmin, joe):
    # GIVEN
    plugin._automation_enabled = True
    plugin._total_slots = 2
    plugin._min_free_slots = 1
    plugin._delay = .1
    joe.kick = Mock()
    # WHEN
    superadmin.connects(0)
    joe.connects(1)
    # THEN
    time.sleep(.2)
    assert [call(reason='to free a slot', silent=True, keyword='makeroom')] == joe.kick.mock_calls


def test_no_kick_non_member_when_on_and_enough_free_slots(plugin, superadmin, joe):
    # GIVEN
    plugin._automation_enabled = True
    plugin._total_slots = 3
    plugin._min_free_slots = 1
    joe.kick = Mock()
    # WHEN
    superadmin.connects(0)
    joe.connects(1)
    # THEN
    assert [] == joe.kick.mock_calls


def test_no_kick_member_when_off(plugin, superadmin, joe):
    # GIVEN
    plugin._automation_enabled = False
    plugin._total_slots = 2
    plugin._min_free_slots = 1
    joe._groupBits = 8
    joe.kick = Mock()
    # WHEN
    superadmin.connects(0)
    joe.connects(1)
    # THEN
    assert [] == joe.kick.mock_calls


def test_no_kick_non_member_when_off(plugin, superadmin, joe):
    # GIVEN
    plugin._automation_enabled = False
    plugin._total_slots = 2
    plugin._min_free_slots = 1
    joe.kick = Mock()
    # WHEN
    superadmin.connects(0)
    joe.connects(1)
    # THEN
    assert [] == joe.kick.mock_calls


def test_automation_without_admin_does_not_crash(plugin, superadmin, joe):
    # GIVEN the automation frees a slot: cmd_makeroom is called without client
    plugin._retain_free_duration = 0
    joe.kick = Mock()
    superadmin.connects(0)
    joe.connects(1)
    # WHEN
    plugin.cmd_makeroom()
    # THEN
    assert [call(admin=None, reason='to free a slot', silent=True, keyword='makeroom')] == joe.kick.mock_calls
    assert plugin._kick_in_progress.acquire(False)
    plugin._kick_in_progress.release()


def test_automation_without_admin_with_retain_free_duration(plugin, superadmin, joe):
    plugin._retain_free_duration = 30
    joe.kick = Mock()
    superadmin.connects(0)
    joe.connects(1)
    # WHEN
    plugin.cmd_makeroom()
    # THEN
    assert 1 == len(joe.kick.mock_calls)
    assert plugin._retain_free_slot_info['admin'] is None
    # a 2nd request while the slot is retained does not crash either
    plugin.cmd_makeroom()
    assert 1 == len(joe.kick.mock_calls)


def test_automation_without_admin_kick_in_progress(plugin):
    assert plugin._kick_in_progress.acquire(False)
    try:
        plugin.cmd_makeroom()
    finally:
        plugin._kick_in_progress.release()


def test_automation_without_admin_no_non_member(plugin, superadmin):
    superadmin.connects(0)
    plugin.cmd_makeroom()
    assert plugin._kick_in_progress.acquire(False)
    plugin._kick_in_progress.release()
