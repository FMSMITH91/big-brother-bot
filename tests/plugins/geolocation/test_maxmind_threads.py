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
import threading
import time
import unittest

import b3.plugins.geolocation as geolocation_module
from b3.plugins.geolocation.lib.geoip import GeoIP

GEOIP_DB = os.path.join(os.path.dirname(geolocation_module.__file__), 'lib', 'geoip', 'db', 'GeoIP.dat')


class SlowFile(object):
    """
    File wrapper yielding the CPU between seek and read to make thread interleaving likely.
    """
    def __init__(self, fh):
        self.fh = fh

    def seek(self, *args):
        result = self.fh.seek(*args)
        time.sleep(0.0001)
        return result

    def read(self, *args):
        data = self.fh.read(*args)
        time.sleep(0.0001)
        return data

    def close(self):
        self.fh.close()


@unittest.skipUnless(os.path.isfile(GEOIP_DB), "MaxMind GeoIP.dat database not available")
class Test_maxmind_threads(unittest.TestCase):

    IPS = ['8.8.8.8', '193.51.24.1', '151.1.1.1', '1.1.1.1', '202.12.27.33', '81.2.69.160']

    def test_concurrent_lookups(self):
        gi = GeoIP.open(GEOIP_DB, GeoIP.GEOIP_STANDARD)
        self.addCleanup(gi.fh.close)
        expected = dict((ip, gi.id_by_addr(ip)) for ip in self.IPS)
        self.assertGreater(len(set(expected.values())), 1)
        gi.fh = SlowFile(gi.fh)
        errors = []

        def worker(ip):
            for _ in range(20):
                try:
                    result = gi.id_by_addr(ip)
                except Exception as err:
                    errors.append((ip, err))
                    return
                if result != expected[ip]:
                    errors.append((ip, result))

        threads = [threading.Thread(target=worker, args=(ip,)) for ip in self.IPS]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual([], errors)
