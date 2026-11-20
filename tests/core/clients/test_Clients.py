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

import b3

from b3.clients import Clients, Client
from tests import B3TestCase
from unittest.mock import Mock, patch


class TestClients(B3TestCase):
    clients = None
    joe = None
    
    def setUp(self):
        B3TestCase.setUp(self)
        Clients.authorizeClients = Mock()
        self.clients = self.console.clients
        self.clients.newClient(1, name='joe', guid="joe_guid")
        self.clients.newClient(2, name=' H a    x\t0r', guid="haxor_guid")


    def test_getClientsByName(self):
        clients = self.clients.getClientsByName('joe')
        self.assertEqual(1, len(clients))
        self.assertEqual(1, clients[0].cid)
        
        clients = self.clients.getClientsByName('oe')
        self.assertEqual(1, len(clients))
        self.assertEqual(1, clients[0].cid)
        
        clients = self.clients.getClientsByName('hax')
        self.assertEqual(1, len(clients))
        self.assertEqual(2, clients[0].cid)
        
        clients = self.clients.getClientsByName('qsdfqsdf fqsd fsqd fsd f')
        self.assertEqual([], clients)

    def test_getByDB_when_client_connected(self):
        # GIVEN
        haxor = self.clients[2]
        self.assertIsNotNone(haxor.cid)
        self.assertIsNotNone(haxor.id)
        # WHEN
        clients = self.clients.getByDB('@%s' % haxor.id)
        # THEN
        self.assertEqual(1, len(clients))
        found_client = clients[0]
        self.assertEqual(haxor.id, found_client.id)
        self.assertEqual(2, found_client.cid)
        self.assertEqual(self.console, found_client.console)
        self.assertEqual('H a    x\t0r', found_client.name)
        self.assertEqual(' H a    x\t0r^7', found_client.exactName)

    def test_getByDB_when_client_disconnected(self):
        # GIVEN
        haxor = self.clients[2]
        haxor.disconnect()
        self.assertNotIn(2, self.clients)
        self.assertIsNotNone(haxor.id)
        # WHEN
        clients = self.clients.getByDB('@%s' % haxor.id)
        # THEN
        self.assertEqual(1, len(clients))
        found_client = clients[0]
        self.assertEqual(haxor.id, found_client.id)
        self.assertIsNone(found_client.cid)
        self.assertEqual(self.console, found_client.console)
        self.assertEqual('H a    x\t0r', found_client.name)
        self.assertEqual('H a    x\t0r^7', found_client.exactName)


    @patch.object(b3.events, 'Event')
    def test_disconnect(self, Event_mock):
        joe = self.clients.getByCID(1)
        self.assertIsInstance(joe, Client)
        self.assertTrue(1 in self.clients)
        self.assertEqual(joe, self.clients[1])

        self.assertEqual(2, len(self.clients))
        self.clients.disconnect(joe)
        self.assertEqual(1, len(self.clients))

        # verify that the Client object is removed from Clients
        self.assertFalse(1 in self.clients)
        self.assertIsNone(self.clients.getByCID(1))
        self.assertIsNone(self.clients.getByName('joe'))

        # verify that an proper event was fired
        Event_mock.assert_called_once_with(b3.events.EVT_CLIENT_DISCONNECT, 1, joe, None)

    def test_sync_with_none_keeps_clients(self):
        # a parser whose sync() returns None (server could not be queried) must not crash Clients.sync()
        # nor wipe the list of connected clients
        with patch.object(self.console, 'sync', return_value=None):
            self.clients.sync()
        self.assertIsNotNone(self.clients.getByCID(1))
        self.assertIsNotNone(self.clients.getByCID(2))


class TestClients_lookupByName(B3TestCase):
    """
    lookupByName must match the names stored in the database literally: quotes and backslashes used to be escaped
    twice (never matching on SQLite) and LIKE wildcards were not escaped at all.
    """

    def setUp(self):
        B3TestCase.setUp(self)
        Clients.authorizeClients = Mock()
        self.clients = self.console.clients
        for i, name in enumerate(["O'Neil", 'Say "hi"', 'back\\slash', 'percent%', 'under_score', 'underXscore',
                                  'plain']):
            Client(console=self.console, guid='guid%s' % i, name=name).save()

    def names(self, needle):
        return sorted(c.name for c in self.clients.lookupByName(needle))

    def test_single_quote(self):
        self.assertListEqual(["O'Neil"], self.names("O'Ne"))

    def test_double_quote(self):
        self.assertListEqual(['Say "hi"'], self.names('"hi"'))

    def test_backslash(self):
        self.assertListEqual(['back\\slash'], self.names('k\\s'))

    def test_percent_is_literal(self):
        self.assertListEqual(['percent%'], self.names('%'))

    def test_underscore_is_literal(self):
        self.assertListEqual(['under_score'], self.names('r_s'))

    def test_plain(self):
        self.assertListEqual(['plain'], self.names('lai'))

    def test_no_match(self):
        self.assertListEqual([], self.names('nobody'))


class Test_newClient_once(B3TestCase):
    """
    The UrT smoke test failed now and then: the log reader and the event thread both created the joining player, so
    they were authenticated on one object and their commands were checked on the other.
    """

    def setUp(self):
        B3TestCase.setUp(self)
        self.console.startup()

    def test_same_player_is_not_created_twice(self):
        first = self.console.clients.newClient('3', name='Joe', guid='AAAABBBBCCCCDDDD', ip='1.2.3.4')
        second = self.console.clients.newClient('3', name='Joe', guid='AAAABBBBCCCCDDDD', ip='1.2.3.4')
        self.assertIs(first, second)
        self.assertIs(first, self.console.clients.getByCID('3'))

    def test_other_player_on_the_slot_replaces_it(self):
        first = self.console.clients.newClient('3', name='Joe', guid='AAAABBBBCCCCDDDD', ip='1.2.3.4')
        second = self.console.clients.newClient('3', name='Ann', guid='EEEEFFFF00001111', ip='1.2.3.5')
        self.assertIsNot(first, second)
        self.assertIs(second, self.console.clients.getByCID('3'))

    def test_concurrent_creation(self):
        import threading
        made = []
        start = threading.Event()

        def join():
            start.wait()
            made.append(self.console.clients.newClient('4', name='Bob', guid='1234123412341234', ip='1.2.3.6'))
        threads = [threading.Thread(target=join) for _ in range(8)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join(10)
        self.assertEqual(1, len(set(id(c) for c in made)))
