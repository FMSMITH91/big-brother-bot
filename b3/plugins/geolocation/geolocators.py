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
import b3.clients
import ipaddress
import os
import os.path
import time
import requests

from .exceptions import GeolocalizationError
from .lib.geoip import GeoIP
from .location import Location


class Geolocator(object):

    _timeout = 5

    def __init__(self, *args, **kwargs):
        """
        Object constructor.
        """
        pass

    @staticmethod
    def _getIp(data):
        """
        Extract ip information from the given data
        :param data: The data from where to extract the ip address (a B3 client or an IP string, IPv4 or IPv6)
        :raise GeolocalizationError: if we receive an invalid input data
        :return: string
        """
        if isinstance(data, str):
            ip = data
        elif isinstance(data, b3.clients.Client):
            ip = data.ip
            if not ip:
                raise GeolocalizationError('b3.clients.Client object instance has not ip attribute set')
        else:
            raise GeolocalizationError('invalid argument supplied: %s' % type(data).__name__)
        try:
            return str(ipaddress.ip_address(ip.strip()))
        except ValueError:
            raise GeolocalizationError('invalid ip address string supplied: %s' % ip)

    def getLocation(self, data):
        """
        Retrieve location data
        :param data: A B3 client object or an IP string
        :raise RequestException: When we are not able to retrieve location information
        :return: A Location object initialized with location data
        """
        raise NotImplementedError


class IpWhoIsGeolocator(Geolocator):
    """
    ipwho.is: HTTPS, no API key, 1000 requests per day per server IP on the free endpoint.
    """

    _url = 'https://ipwho.is/%s'

    def getLocation(self, data):
        """
        Retrieve location data
        :param data: A B3 client object or an IP string
        :raise GeolocalizationError: When we are not able to retrieve location information
        :return: A Location object initialized with location data
        """
        ip = self._getIp(data)
        rt = requests.get(self._url % ip, timeout=self._timeout).json()

        if not rt.get('success'):
            raise GeolocalizationError('invalid data returned by the api: %r' % rt.get('message', rt))

        connection = rt.get('connection') or {}
        timezone = rt.get('timezone') or {}
        return Location(country=rt.get('country', None), region=rt.get('region', None), city=rt.get('city', None),
                        cc=rt.get('country_code', None), rc=rt.get('region_code', None),
                        isp=connection.get('isp', None), lat=rt.get('latitude', None), lon=rt.get('longitude', None),
                        timezone=timezone.get('id', None), zipcode=rt.get('postal', None))


class IpApiCoGeolocator(Geolocator):
    """
    ipapi.co: HTTPS, no API key, 1000 requests per day on the free plan.
    """

    _url = 'https://ipapi.co/%s/json/'

    def getLocation(self, data):
        """
        Retrieve location data
        :param data: A B3 client object or an IP string
        :raise GeolocalizationError: When we are not able to retrieve location information
        :return: A Location object initialized with location data
        """
        ip = self._getIp(data)
        rt = requests.get(self._url % ip, timeout=self._timeout, headers={'User-Agent': 'B3'}).json()

        if rt.get('error') or not rt.get('country_code'):
            raise GeolocalizationError('invalid data returned by the api: %r' % rt.get('reason', rt))

        return Location(country=rt.get('country_name', None), region=rt.get('region', None), city=rt.get('city', None),
                        cc=rt.get('country_code', None), rc=rt.get('region_code', None), isp=rt.get('org', None),
                        lat=rt.get('latitude', None), lon=rt.get('longitude', None), timezone=rt.get('timezone', None),
                        zipcode=rt.get('postal', None))


class MmdbGeolocator(Geolocator):
    """
    Offline lookup in a current country database in the MaxMind DB (.mmdb) format: DB-IP "IP to Country Lite"
    (CC BY 4.0, monthly, no account: https://db-ip.com/db/download/ip-to-country-lite) or MaxMind GeoLite2 Country.
    IPv4 and IPv6. No player IP address leaves the machine. The file is supplied by the operator: B3 downloads nothing.
    """

    DEFAULT_PATH = '@home/dbip-country-lite.mmdb'
    # a monthly database older than this is reported as stale (countries of reassigned IP blocks go wrong)
    STALE_AFTER_DAYS = 90

    def __init__(self, path=None, *args, **kwargs):
        """
        Object constructor.
        :param path: The .mmdb file (B3 path prefixes such as @home/ allowed)
        :raise IOError: if the database is missing, unreadable, or the maxminddb module is not installed
        """
        super(MmdbGeolocator, self).__init__(*args, **kwargs)
        self._path = b3.getAbsolutePath(path or self.DEFAULT_PATH, decode=True)
        if not os.path.isfile(self._path):
            raise IOError('no country database at %s' % self._path)
        try:
            import maxminddb
        except ImportError:
            raise IOError('the maxminddb Python module is not installed (pip install maxminddb)')
        try:
            self._reader = maxminddb.open_database(self._path)
        except (ValueError, maxminddb.InvalidDatabaseError) as e:
            raise IOError('%s is not a valid MaxMind DB file: %s' % (self._path, e))
        meta = self._reader.metadata()
        self.database_type = meta.database_type
        self.build_time = time.gmtime(meta.build_epoch)
        self.age_days = int((time.time() - meta.build_epoch) // 86400)

    @property
    def path(self):
        return self._path

    @property
    def is_stale(self):
        return self.age_days > self.STALE_AFTER_DAYS

    def describe(self):
        """
        Return a one line description for the log.
        """
        return '%s (%s, built %s)' % (self._path, self.database_type, time.strftime('%Y-%m-%d', self.build_time))

    def getLocation(self, data):
        """
        Retrieve location data
        :param data: A B3 client object or an IP string
        :raise GeolocalizationError: When we are not able to retrieve location information
        :return: A Location object initialized with location data
        """
        ip = self._getIp(data)
        try:
            record = self._reader.get(ip)
        except ValueError as e:
            raise GeolocalizationError('invalid IP address %r: %s' % (ip, e))
        country = (record or {}).get('country') or {}
        cc = country.get('iso_code')
        if not cc:
            raise GeolocalizationError('no country found for %s in %s' % (ip, self._path))
        return Location(country=(country.get('names') or {}).get('en', None), cc=cc)


class MaxMindGeolocator(Geolocator):

    _path = None
    _geoip = None

    def __init__(self, *args, **kwargs):
        """
        Object constructor.
        :raise IOError: if the database is not available
        """
        super(MaxMindGeolocator, self).__init__(*args, **kwargs)
        # prefer plugin relative path
        self._path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib', 'geoip', 'db', 'GeoIP.dat')
        if not os.path.isfile(self._path):
            # search system wide (using system path according to installation
            # instructions: http://dev.maxmind.com/geoip/legacy/install/country/
            if not os.path.isfile('/usr/local/share/GeoIP/GeoIP.dat'):
                raise IOError('no MaxMind GeoIP.dat database available: put the database file in %s' % self._path)
            self._path = '/usr/local/share/GeoIP/GeoIP.dat'
        self.geoip = GeoIP.open(self._path, GeoIP.GEOIP_STANDARD)

    def getLocation(self, data):
        """
        Retrieve location data
        :param data: A B3 client object or an IP string
        :raise GeolocalizationError: When we are not able to retrieve location information
        :return: A Location object initialized with location data
        """
        ip = self._getIp(data)
        if ':' in ip:
            raise GeolocalizationError('the legacy MaxMind GeoIP.dat database has no IPv6 data (%s)' % ip)
        country_id = self.geoip.id_by_addr(ip)
        return Location(country=GeoIP.id_to_country_name(country_id), cc=GeoIP.id_to_country_code(country_id))