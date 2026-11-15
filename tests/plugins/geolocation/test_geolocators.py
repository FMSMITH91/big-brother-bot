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

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from b3.plugins.geolocation.exceptions import GeolocalizationError
from b3.plugins.geolocation.geolocators import IpApiCoGeolocator
from b3.plugins.geolocation.geolocators import IpWhoIsGeolocator
from b3.plugins.geolocation.geolocators import MaxMindGeolocator
from tests.plugins.geolocation import GeolocationTestCase


def response(data):
    return Mock(json=Mock(return_value=data))


class Test_online_services(GeolocationTestCase):

    def test_only_https_services(self):
        # player IP addresses must not be sent over plain HTTP
        online = [g for g in self.p._geolocators if not isinstance(g, MaxMindGeolocator)]
        self.assertGreaterEqual(len(online), 2)
        for geolocator in online:
            self.assertTrue(geolocator._url.startswith('https://'), geolocator._url)


class Test_IpWhoIsGeolocator(unittest.TestCase):

    @patch('b3.plugins.geolocation.geolocators.requests.get')
    def test_success(self, get):
        get.return_value = response({
            'ip': '8.8.8.8', 'success': True, 'country': 'United States', 'country_code': 'US',
            'region': 'California', 'region_code': 'CA', 'city': 'Mountain View', 'latitude': 37.4,
            'longitude': -122.1, 'postal': '94043', 'connection': {'isp': 'Google LLC'},
            'timezone': {'id': 'America/Los_Angeles'}})
        location = IpWhoIsGeolocator().getLocation('8.8.8.8')
        get.assert_called_once_with('https://ipwho.is/8.8.8.8', timeout=IpWhoIsGeolocator._timeout)
        self.assertEqual(('United States', 'US', 'California', 'CA', 'Mountain View', 'Google LLC'),
                         (location.country, location.cc, location.region, location.rc, location.city, location.isp))
        self.assertEqual(('37.4', '-122.1', 'America/Los_Angeles', '94043'),
                         (location.lat, location.lon, location.timezone, location.zipcode))

    @patch('b3.plugins.geolocation.geolocators.requests.get')
    def test_failure(self, get):
        get.return_value = response({'ip': '10.0.0.1', 'success': False, 'message': 'Reserved range'})
        self.assertRaises(GeolocalizationError, IpWhoIsGeolocator().getLocation, '10.0.0.1')


class Test_IpApiCoGeolocator(unittest.TestCase):

    @patch('b3.plugins.geolocation.geolocators.requests.get')
    def test_success(self, get):
        get.return_value = response({
            'ip': '8.8.8.8', 'city': 'Mountain View', 'region': 'California', 'region_code': 'CA',
            'country_code': 'US', 'country_name': 'United States', 'postal': '94043', 'latitude': 37.4,
            'longitude': -122.1, 'timezone': 'America/Los_Angeles', 'org': 'GOOGLE'})
        location = IpApiCoGeolocator().getLocation('8.8.8.8')
        self.assertEqual('https://ipapi.co/8.8.8.8/json/', get.call_args[0][0])
        self.assertEqual(('United States', 'US', 'California', 'Mountain View', 'GOOGLE', 'America/Los_Angeles'),
                         (location.country, location.cc, location.region, location.city, location.isp,
                          location.timezone))

    @patch('b3.plugins.geolocation.geolocators.requests.get')
    def test_failure(self, get):
        get.return_value = response({'ip': '10.0.0.1', 'error': True, 'reason': 'Reserved IP Address'})
        self.assertRaises(GeolocalizationError, IpApiCoGeolocator().getLocation, '10.0.0.1')
