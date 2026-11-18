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

__author__ = 'Fenix'
__version__ = '1.8'

import b3
import b3.clients
import b3.plugin
import b3.events
import threading

from .exceptions import GeolocalizationError
from .geolocators import IpApiCoGeolocator
from .geolocators import IpWhoIsGeolocator
from .geolocators import MaxMindGeolocator
from .geolocators import MmdbGeolocator


# services by the name used in the "geolocators" setting (plugin_geolocation.ini)
GEOLOCATORS = {
    'ipwho.is': IpWhoIsGeolocator,
    'ipapi.co': IpApiCoGeolocator,
    'mmdb': MmdbGeolocator,
    'maxmind': MaxMindGeolocator,
}
GEOLOCATOR_ALIASES = {'ipwho': 'ipwho.is', 'ipapi': 'ipapi.co', 'dbip': 'mmdb', 'geolite2': 'mmdb'}
# online services first (they know the city, region and ISP), over HTTPS only: player IP addresses must not cross
# the internet in clear text. Then the offline country databases: a current .mmdb file if the operator supplied one
# (mmdb_file), and the MaxMind GeoIP.dat bundled with B3 (2015, IPv4 only) as the last resort.
DEFAULT_GEOLOCATORS = ('ipwho.is', 'ipapi.co', 'mmdb', 'maxmind')


class GeolocationPlugin(b3.plugin.Plugin):

    requiresConfigFile = False

    def __init__(self, console, config=None):
        """
        Build the plugin object.
        """
        b3.plugin.Plugin.__init__(self, console, config)
        self.info('creating geolocators object instances...')
        self._mmdb_file = MmdbGeolocator.DEFAULT_PATH
        self._geolocators = self._build_geolocators(DEFAULT_GEOLOCATORS)

    def onLoadConfig(self):
        """
        Load the plugin configuration: "geolocators" picks the services and their order, "mmdb_file" is the offline
        country database used by the mmdb service.
        """
        self._mmdb_file = MmdbGeolocator.DEFAULT_PATH
        if self.config and self.config.has_option('settings', 'mmdb_file'):
            self._mmdb_file = self.config.get('settings', 'mmdb_file').strip() or MmdbGeolocator.DEFAULT_PATH
        self._geolocators = self._build_geolocators(self._geolocator_names())
        self.info('geolocation services, in order: %s',
                  ', '.join(self._geolocator_name(g) for g in self._geolocators) or 'none')
        for geolocator in self._geolocators:
            if isinstance(geolocator, MmdbGeolocator):
                # CC BY 4.0 (DB-IP Lite) asks for attribution: https://db-ip.com
                self.info('offline country database: %s', geolocator.describe())
                if geolocator.is_stale:
                    self.warning('offline country database %s is %s days old: download the current one (DB-IP Lite '
                                 'is updated monthly)', geolocator.path, geolocator.age_days)

    def _geolocator_names(self):
        """
        Read [settings] geolocators: a comma separated list of service names (ipwho.is, ipapi.co, maxmind).
        Unknown names are skipped; a missing or empty setting keeps the default order.
        """
        if not self.config or not self.config.has_option('settings', 'geolocators'):
            return DEFAULT_GEOLOCATORS
        names = []
        for raw in self.config.get('settings', 'geolocators').split(','):
            name = raw.strip().lower()
            if not name:
                continue
            name = GEOLOCATOR_ALIASES.get(name, name)
            if name not in GEOLOCATORS:
                self.warning('unknown geolocation service %r in settings/geolocators: expected one of %s',
                             raw.strip(), ', '.join(sorted(GEOLOCATORS)))
            elif name not in names:
                names.append(name)
        if not names:
            self.warning('no valid geolocation service in settings/geolocators: using the default (%s)',
                         ', '.join(DEFAULT_GEOLOCATORS))
            return DEFAULT_GEOLOCATORS
        return tuple(names)

    def _build_geolocators(self, names):
        """
        Create the geolocator objects for the given service names, in order.
        """
        geolocators = []
        for name in names:
            try:
                if name == 'mmdb':
                    geolocators.append(MmdbGeolocator(self._mmdb_file))
                else:
                    geolocators.append(GEOLOCATORS[name]())
            except IOError as e:
                # an offline database may be missing: only worth a warning when it was asked for explicitly
                log = self.debug if names is DEFAULT_GEOLOCATORS else self.warning
                log('%s geolocation not available: %s', name, e)
        return geolocators

    @staticmethod
    def _geolocator_name(geolocator):
        for name, clazz in GEOLOCATORS.items():
            if isinstance(geolocator, clazz):
                return name
        return geolocator.__class__.__name__

    def onStartup(self):
        """
        Initialize plugin.
        """
        # register events needed
        if self.console.isFrostbiteGame():
            self.registerEvent('EVT_PUNKBUSTER_NEW_CONNECTION', self.geolocate)
        else:
            self.registerEvent('EVT_CLIENT_AUTH', self.geolocate)

        self.registerEvent('EVT_CLIENT_UPDATE', self.geolocate)

        # create our custom events so other plugins can react when clients are geolocated
        self.console.createEvent('EVT_CLIENT_GEOLOCATION_SUCCESS', 'Event client geolocation success')
        self.console.createEvent('EVT_CLIENT_GEOLOCATION_FAILURE', 'Event client geolocation failure')

    ####################################################################################################################
    #                                                                                                                  #
    #   EVENTS                                                                                                         #
    #                                                                                                                  #
    ####################################################################################################################

    def geolocate(self, event):
        """
        Handle EVT_CLIENT_AUTH and EVT_CLIENT_UPDATE.
        """
        def _threaded_geolocate(client):

            client.location = None

            for geotool in self._geolocators:

                try:
                    self.debug('retrieving geolocation data for %s <@%s>...', client.name, client.id)
                    client.location = geotool.getLocation(client)
                    self.debug('retrieved geolocation data for %s <@%s>: %r', client.name, client.id, client.location)
                    break # stop iterating if we collect valid data
                except GeolocalizationError as e:
                    self.warning('could not retrieve geolocation data %s <@%s>: %s', client.name, client.id, e)
                except Exception as e:
                    self.error('client %s <@%s> geolocation terminated unexpectedtly when using %s service: %s',
                               client.name, client.id, geotool.__class__.__name__, e)

            if client.location is not None:
                self.console.queueEvent(self.console.getEvent('EVT_CLIENT_GEOLOCATION_SUCCESS', client=client))
            else:
                self.console.queueEvent(self.console.getEvent('EVT_CLIENT_GEOLOCATION_FAILURE', client=client))

        # do not use hasattr or try except here: we'd better try to get geodata also when a previous attempt failed
        # and we ended up with NoneType object in client.location (so we have an attribute but it's not useful).
        # also make sure to launch geolocation only if we have a valid ip address.
        if not getattr(event.client, 'location', None) and event.client.ip:
            t = threading.Thread(target=_threaded_geolocate, args=(event.client,))
            t.daemon = True  # won't prevent B3 from exiting
            t.start()