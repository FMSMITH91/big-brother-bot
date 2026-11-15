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

import io
import feedparser

from b3.fake import FakeClient
from unittest.mock import patch, call, Mock
from mockito import when, any as ANY
from tests.plugins.adv import AdvTestCase, RSS_FEED_CONTENT

class Test_keywords(AdvTestCase):

    def setUp(self):
        AdvTestCase.setUp(self)
        self.init_plugin()

    def test_admins(self):
        # GIVEN
        when(self.p._msg).getnext().thenReturn("@admins")
        joe = FakeClient(self.console, name="Joe", guid="joeguid", groupBits=128)
        when(self.p._adminPlugin).getAdmins().thenReturn([joe])
        with patch.object(self.console, "say") as say_mock:
            # WHEN
            self.p.adv()
        # THEN
        say_mock.assert_has_calls([call('^7Admins online: Joe^7^7 [^3100^7]')])

    def test_regulars(self):
        # GIVEN
        when(self.p._msg).getnext().thenReturn("@regulars")
        joe = FakeClient(self.console, name="Joe", guid="joeguid", groupBits=2)
        when(self.p._adminPlugin).getRegulars().thenReturn([joe])
        with patch.object(self.console, "say") as say_mock:
            # WHEN
            self.p.adv()
        # THEN
        say_mock.assert_has_calls([call('^7Regular players online: Joe^7')])

    def test_topstats(self):
        when(self.p._msg).getnext().thenReturn("@topstats")
        self.p._xlrstatsPlugin = Mock()
        with patch.object(self.p._xlrstatsPlugin, "cmd_xlrtopstats") as xlrtopstats_mock:
            self.p.adv()
            xlrtopstats_mock.assert_has_calls([call(ext=True, cmd=None, data='3', client=None)])

    def test_time(self):
        when(self.p._msg).getnext().thenReturn("@time")
        when(self.console).formatTime(ANY()).thenReturn("f00")
        with patch.object(self.console, "say") as say_mock:
            self.p.adv()
            say_mock.assert_has_calls([call('^2Time: ^3f00')])

    def test_nextmap(self):
        when(self.p._msg).getnext().thenReturn("@nextmap")
        when(self.console).getNextMap().thenReturn("f00")
        with patch.object(self.console, "say") as say_mock:
            self.p.adv()
            say_mock.assert_has_calls([call('^2Next map: ^3f00')])

    def test_feed(self):
        # GIVEN
        self.p._feed = "http://some.feed/rss"

        when(self.p._msg).getnext().thenReturn("@feed")
        # feedparser >= 6 moved _open_resource to feedparser.api and expects it to return bytes
        with patch.object(feedparser.api, '_open_resource', return_value=RSS_FEED_CONTENT.encode('utf-8')):
            with patch.object(self.console, "say") as say_mock:
                self.p.adv()
                say_mock.assert_has_calls([call('News: f00 bar item title')])
    def test_feed_item_number(self):
        # GIVEN
        self.p._feed = "http://some.feed/rss"
        items = "".join("<item><title>item %s</title><link>http://some.feed/%s</link></item>" % (n, n)
                        for n in range(3))
        content = RSS_FEED_CONTENT.replace(RSS_FEED_CONTENT[RSS_FEED_CONTENT.index('<item>'):
                                                            RSS_FEED_CONTENT.index('</item>') + 7], items)
        when(self.p._msg).getnext().thenReturn("@feed 2")
        with patch.object(feedparser.api, '_open_resource', return_value=content.encode('utf-8')):
            with patch.object(self.console, "say") as say_mock:
                # WHEN
                self.p.adv()
                # THEN
                say_mock.assert_has_calls([call('News: item 2')])
        self.assertEqual(3, self.p._feeditemnr)

    def test_feed_invalid_item_number(self):
        self.p._feed = "http://some.feed/rss"
        with patch('feedparser.parse', return_value={'bozo': 0, 'entries': []}) as parse_mock:
            self.assertIsNone(self.p.get_feed("@feed foo"))
        self.assertFalse(parse_mock.called)
