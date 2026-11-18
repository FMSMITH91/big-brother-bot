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

import os
import shutil
import tempfile
import time
import unittest

from unittest.mock import patch
from b3.config import CfgConfigParser
from b3.plugins.geolocation import GeolocationPlugin
from b3.plugins.geolocation.exceptions import GeolocalizationError
from b3.plugins.geolocation.geolocators import IpWhoIsGeolocator
from b3.plugins.geolocation.geolocators import MaxMindGeolocator
from b3.plugins.geolocation.geolocators import MmdbGeolocator
from tests import B3TestCase
from tests.plugins.geolocation.mmdb_writer import write_mmdb

NETWORKS = {
    '81.0.0.0/8': {'country': {'iso_code': 'IT', 'names': {'en': 'Italy', 'de': 'Italien'}}},
    '2001:db8::/32': {'country': {'iso_code': 'DE', 'names': {'en': 'Germany'}}},
    '10.0.0.0/8': {'continent': {'code': 'EU'}},  # a record without a country
}


class MmdbTestCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = os.path.join(self.dir, 'dbip-country-lite.mmdb')
        write_mmdb(self.path, NETWORKS, build_epoch=int(time.time()) - 86400 * 10)


class Test_MmdbGeolocator(MmdbTestCase):
    """
    A current offline country database (DB-IP Lite or GeoLite2, .mmdb): the bundled GeoIP.dat is from 2015 and IPv4 only.
    """

    def test_ipv4(self):
        location = MmdbGeolocator(self.path).getLocation('81.2.3.4')
        self.assertEqual(('Italy', 'IT'), (location.country, location.cc))
        self.assertIsNone(location.city)

    def test_ipv6(self):
        location = MmdbGeolocator(self.path).getLocation('2001:db8::1')
        self.assertEqual(('Germany', 'DE'), (location.country, location.cc))

    def test_address_not_in_database(self):
        with self.assertRaises(GeolocalizationError):
            MmdbGeolocator(self.path).getLocation('82.1.1.1')

    def test_record_without_country(self):
        with self.assertRaises(GeolocalizationError):
            MmdbGeolocator(self.path).getLocation('10.1.2.3')

    def test_invalid_address(self):
        with self.assertRaises(GeolocalizationError):
            MmdbGeolocator(self.path).getLocation('not an ip')

    def test_missing_file(self):
        with self.assertRaises(IOError):
            MmdbGeolocator(os.path.join(self.dir, 'nope.mmdb'))

    def test_not_a_database(self):
        bad = os.path.join(self.dir, 'bad.mmdb')
        with open(bad, 'wb') as f:
            f.write(b'<html>not found</html>')
        with self.assertRaises(IOError):
            MmdbGeolocator(bad)

    def test_pure_python_reader(self):
        # the maxminddb C extension may be missing on some platforms: the pure Python reader must read the file too
        import maxminddb
        reader = maxminddb.open_database(self.path, maxminddb.MODE_FILE)
        self.assertEqual('IT', reader.get('81.2.3.4')['country']['iso_code'])

    def test_describe_and_age(self):
        g = MmdbGeolocator(self.path)
        self.assertIn('DBIP-Country-Lite', g.describe())
        self.assertIn(time.strftime('%Y-%m-%d', time.gmtime(time.time() - 86400 * 10)), g.describe())
        self.assertFalse(g.is_stale)
        old = os.path.join(self.dir, 'old.mmdb')
        write_mmdb(old, NETWORKS, build_epoch=int(time.time()) - 86400 * 200)
        self.assertTrue(MmdbGeolocator(old).is_stale)

    def test_maxminddb_not_installed(self):
        with patch.dict('sys.modules', {'maxminddb': None}):
            with self.assertRaises(IOError):
                MmdbGeolocator(self.path)


class Test_ip_addresses(unittest.TestCase):

    def test_ipv6_accepted(self):
        self.assertEqual('2001:db8::1', IpWhoIsGeolocator._getIp('2001:DB8:0::1'))

    def test_ipv4_accepted(self):
        self.assertEqual('81.2.3.4', IpWhoIsGeolocator._getIp(' 81.2.3.4 '))

    def test_garbage_rejected(self):
        for value in ('', '81.2.3', '999.1.1.1', 'localhost'):
            with self.assertRaises(GeolocalizationError, msg=value):
                IpWhoIsGeolocator._getIp(value)

    def test_legacy_database_rejects_ipv6(self):
        with self.assertRaises(GeolocalizationError):
            MaxMindGeolocator().getLocation('2001:db8::1')


class Test_plugin_mmdb(MmdbTestCase, B3TestCase):

    def setUp(self):
        B3TestCase.setUp(self)
        MmdbTestCase.setUp(self)

    def plugin(self, ini):
        conf = CfgConfigParser()
        conf.loadFromString(ini)
        p = GeolocationPlugin(self.console, conf)
        with patch.object(p, 'warning') as warning, patch.object(p, 'info') as info:
            p.onLoadConfig()
        return p, warning, info

    def test_offline_only(self):
        p, warning, info = self.plugin('[settings]\ngeolocators: dbip, maxmind\nmmdb_file: %s\n' % self.path)
        self.assertEqual([MmdbGeolocator, MaxMindGeolocator], [g.__class__ for g in p._geolocators])
        self.assertEqual('IT', p._geolocators[0].getLocation('81.2.3.4').cc)
        warning.assert_not_called()
        self.assertTrue(any('offline country database' in c[0][0] for c in info.call_args_list))

    def test_default_order_uses_the_file_when_present(self):
        p, warning, info = self.plugin('[settings]\nmmdb_file: %s\n' % self.path)
        self.assertEqual(['ipwho.is', 'ipapi.co', 'mmdb', 'maxmind'], [p._geolocator_name(g) for g in p._geolocators])

    def test_default_order_skips_a_missing_file_quietly(self):
        p, warning, info = self.plugin('[settings]\nmmdb_file: %s\n' % os.path.join(self.dir, 'nope.mmdb'))
        self.assertEqual(['ipwho.is', 'ipapi.co', 'maxmind'], [p._geolocator_name(g) for g in p._geolocators])
        warning.assert_not_called()

    def test_missing_file_asked_for_is_a_warning(self):
        p, warning, info = self.plugin('[settings]\ngeolocators: mmdb\nmmdb_file: %s\n' % os.path.join(self.dir, 'nope'))
        self.assertEqual([], p._geolocators)
        warning.assert_called_once()

    def test_stale_database_is_a_warning(self):
        old = os.path.join(self.dir, 'old.mmdb')
        write_mmdb(old, NETWORKS, build_epoch=int(time.time()) - 86400 * 200)
        p, warning, info = self.plugin('[settings]\ngeolocators: mmdb\nmmdb_file: %s\n' % old)
        warning.assert_called_once()
        self.assertIn('days old', warning.call_args[0][0])
