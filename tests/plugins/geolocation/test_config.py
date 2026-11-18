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

from b3.config import CfgConfigParser
from b3.plugins.geolocation import GeolocationPlugin
from b3.plugins.geolocation.geolocators import IpApiCoGeolocator
from b3.plugins.geolocation.geolocators import IpWhoIsGeolocator
from b3.plugins.geolocation.geolocators import MaxMindGeolocator
from tests import B3TestCase


class Test_geolocators_setting(B3TestCase):
    """
    linuxgsm-panel (2026-11-18): its network lock can relay a single HTTPS service, so lookups to the other one failed
    quietly. The geolocators setting picks the services, and lets the owner choose who sees player IP addresses.
    """

    def plugin(self, ini=None):
        conf = CfgConfigParser()
        conf.loadFromString(ini or '')
        p = GeolocationPlugin(self.console, conf)
        p.onLoadConfig()
        return p

    def classes(self, p):
        return [g.__class__ for g in p._geolocators]

    def test_default_without_setting(self):
        p = self.plugin()
        self.assertEqual([IpWhoIsGeolocator, IpApiCoGeolocator, MaxMindGeolocator], self.classes(p))

    def test_default_without_config(self):
        p = GeolocationPlugin(self.console)
        p.onLoadConfig()
        self.assertEqual([IpWhoIsGeolocator, IpApiCoGeolocator, MaxMindGeolocator], self.classes(p))

    def test_single_service(self):
        p = self.plugin('[settings]\ngeolocators: ipwho\n')
        self.assertEqual([IpWhoIsGeolocator], self.classes(p))

    def test_order_aliases_case_and_duplicates(self):
        p = self.plugin('[settings]\ngeolocators: MaxMind, ipapi.co, ipapi, ipwho.is\n')
        self.assertEqual([MaxMindGeolocator, IpApiCoGeolocator, IpWhoIsGeolocator], self.classes(p))

    def test_offline_only(self):
        p = self.plugin('[settings]\ngeolocators: maxmind\n')
        self.assertEqual([MaxMindGeolocator], self.classes(p))

    def test_unknown_names_are_skipped(self):
        p = self.plugin('[settings]\ngeolocators: ip-api.com, ipapi.co\n')
        self.assertEqual([IpApiCoGeolocator], self.classes(p))

    def test_nothing_valid_falls_back_to_default(self):
        p = self.plugin('[settings]\ngeolocators: nope, \n')
        self.assertEqual([IpWhoIsGeolocator, IpApiCoGeolocator, MaxMindGeolocator], self.classes(p))

    def test_sample_config_is_the_default(self):
        sample = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'b3', 'conf', 'plugin_geolocation.ini')
        with open(sample, encoding='utf-8') as f:
            p = self.plugin(f.read())
        self.assertEqual([IpWhoIsGeolocator, IpApiCoGeolocator, MaxMindGeolocator], self.classes(p))
