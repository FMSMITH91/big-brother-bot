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
import b3.config
import json
import os
import re
import sys
import urllib.request, urllib.error, urllib.parse

import functools
from time import sleep

## GitHub repository whose releases are checked for updates (the old master.bigbrotherbot.net
## version.json endpoint no longer exists)
B3_GITHUB_REPOSITORY = 'FMSMITH91/big-brother-bot'
URL_B3_LATEST_VERSION = 'https://api.github.com/repos/%s/releases?per_page=50' % B3_GITHUB_REPOSITORY

## supported update channels
UPDATE_CHANNEL_STABLE = 'stable'
UPDATE_CHANNEL_BETA = 'beta'
UPDATE_CHANNEL_DEV = 'dev'


def _cmp(a, b):
    """
    Python 3 replacement for the removed cmp() builtin.
    """
    return (a > b) - (a < b)


@functools.total_ordering
class B3version(object):
    """
    Version numbering for BigBrotherBot.
    Compared to version.StrictVersion this class allows version numbers such as :
        1.0dev
        1.0dev2
        1.0d3
        1.0a
        1.0a
        1.0a34
        1.0b
        1.0b1
        1.0b3
        1.9.0dev7.daily21-20121004
    And make sure that any 'dev' prerelease is inferior to any 'alpha' prerelease
    """
    version = None
    prerelease = None
    build_num = None

    version_re = re.compile(r'''^
(?P<major>\d+)\.(?P<minor>\d+)   # 1.2
(?:\. (?P<patch>\d+))?           # 1.2.45
(?P<prerelease>                  # 1.2.45b2
  (?P<tag>a|b|dev)
  (?P<tag_num>\d+)?
)?                                                                     # 1.2.45b2.devd94d71a-20120901
((?P<daily>\.daily(?P<build_num>\d+?))|(?P<dev>\.dev(?P<dev_num>\w+?)) # 1.2.45b2.daily4-20120901
)?
(?:-(?P<date>20\d\d\d\d\d\d))?   # 1.10.0dev-20150215
$''', re.VERBOSE)
    prerelease_order = {'dev': 0, 'a': 1, 'b': 2}

    def __init__(self, vstring=None):
        if vstring:
            self.parse(vstring)

    def __str__(self):
        if self.version[2] == 0:
            vstring = '.'.join(map(str, self.version[0:2]))
        else:
            vstring = '.'.join(map(str, self.version))
        if self.prerelease:
            vstring = vstring + self.prerelease[0] + str(self.prerelease[1])
        return vstring

    def __repr__(self):
        return "%s ('%s')" % (self.__class__.__name__, str(self))

    def __eq__(self, other):
        return self._cmp(other) == 0

    def __lt__(self, other):
        return self._cmp(other) < 0

    def __hash__(self):
        return hash((self.version, self.prerelease, self.build_num))

    def parse (self, vstring):
        """
        Parse the version number from a string.
        :param vstring: The version string
        """
        match = self.version_re.match(vstring)
        if not match:
            raise ValueError("invalid version number '%s'" % vstring)

        major = match.group('major')
        minor = match.group('minor')

        patch = match.group('patch')
        if patch:
            self.version = tuple(map(int, [major, minor, patch]))
        else:
            self.version = tuple(list(map(int, [major, minor])) + [0])

        prerelease = match.group('tag')
        prerelease_num = match.group('tag_num')
        if prerelease:
            self.prerelease = (prerelease, int(prerelease_num if prerelease_num else '0'))
        else:
            self.prerelease = None

        daily_num = match.group('build_num')
        if daily_num:
            self.build_num = int(daily_num if daily_num else '0')
        else:
            self.build_num = None

    def _cmp(self, other):
        """
        Compare current object with another one.
        :param other: The other object
        """
        if isinstance(other, str):
            other = B3version(other)

        compare = _cmp(self.version, other.version)
        if compare != 0:
            return compare

        # we have to compare prerelease
        compare = self.__cmp_prerelease(other)
        if compare != 0:
            return compare

        # we have to compare build num
        return self.__cmp_build(other)

    def __cmp_prerelease(self, other):
        # case 1: neither has prerelease; they're equal
        # case 2: self has prerelease, other doesn't; other is greater
        # case 3: self doesn't have prerelease, other does: self is greater
        # case 4: both have prerelease: must compare them!
        if not self.prerelease and not other.prerelease:
            return 0
        elif self.prerelease and not other.prerelease:
            return -1
        elif not self.prerelease and other.prerelease:
            return 1
        elif self.prerelease and other.prerelease:
            return _cmp((self.prerelease_order[self.prerelease[0]], self.prerelease[1]),
                       (self.prerelease_order[other.prerelease[0]], other.prerelease[1]))

    def __cmp_build(self, other):
        # case 1: neither has build_num; they're equal
        # case 2: self has build_num, other doesn't; other is greater
        # case 3: self doesn't have build_num, other does: self is greater
        # case 4: both have build_num: must compare them!
        if not self.build_num and not other.build_num:
            return 0
        elif self.build_num and not other.build_num:
            return -1
        elif not self.build_num and other.build_num:
            return 1
        elif self.build_num and other.build_num:
            return _cmp(self.build_num, other.build_num)


def getDefaultChannel(currentVersion):
    """
    Return an update channel according to the current B3 version.
    :param currentVersion: The B3 version to use to compute the update channel
    """
    if currentVersion is None:
        return UPDATE_CHANNEL_STABLE

    version_re = re.compile(r'''^
(?P<major>\d+)\.(?P<minor>\d+)   # 1.2
(?:\. (?P<patch>\d+))?           # 1.2.45
(?P<prerelease>                  # 1.2.45b2
  (?P<tag>a|b|dev)
  (?P<tag_num>\d+)?
)?
(?P<daily>                       # 1.2.45b2.daily4-20120901
    \.daily(?P<build_num>\d+?)
    (?:-20\d\d\d\d\d\d)?
)?
$''', re.VERBOSE)

    m = version_re.match(currentVersion)
    if not m or m.group('tag') is None:
        return UPDATE_CHANNEL_STABLE
    elif m.group('tag').lower() in ('dev', 'a'):
        return UPDATE_CHANNEL_DEV
    elif m.group('tag').lower() == 'b':
        return UPDATE_CHANNEL_BETA


def _channels_from_github_releases(releases):
    """
    Turn the GitHub releases API response into the {'B3': {'channels': {...}}} structure the old
    version.json used: the stable channel offers final releases only, beta also offers alpha/beta
    pre-releases, and dev offers everything. Drafts and tags that are not B3 version numbers are ignored.
    """
    order = {UPDATE_CHANNEL_STABLE: 0, UPDATE_CHANNEL_BETA: 1, UPDATE_CHANNEL_DEV: 2}
    channels = {}
    for release in releases:
        if release.get('draft'):
            continue
        tag = (release.get('tag_name') or '').strip()
        if tag[:1] in ('v', 'V'):
            tag = tag[1:]
        try:
            version = B3version(tag)
        except ValueError:
            continue
        if version.prerelease and version.prerelease[0] == 'dev':
            kind = UPDATE_CHANNEL_DEV
        elif version.prerelease or version.build_num or release.get('prerelease'):
            kind = UPDATE_CHANNEL_BETA
        else:
            kind = UPDATE_CHANNEL_STABLE
        for name, level in order.items():
            if order[kind] > level:
                continue  # e.g. a beta is not offered on the stable channel
            current = channels.get(name)
            if current is None or B3version(current['latest-version']) < version:
                channels[name] = {'latest-version': tag, 'url': release.get('html_url')}
    return {'B3': {'channels': channels}}


def checkUpdate(currentVersion, channel=None, singleLine=True, showErrormsg=False, timeout=4):
    """
    Check if an update of B3 is available.
    """
    if channel is None:
        channel = getDefaultChannel(currentVersion)

    if not singleLine:
        sys.stdout.write("checking for updates... \n")

    message = None
    errormessage = None
    
    try:
        request = urllib.request.Request(URL_B3_LATEST_VERSION, headers={'Accept': 'application/vnd.github+json',
                                                                         'User-Agent': 'b3-update-check'})
        json_data = urllib.request.urlopen(request, timeout=timeout).read()
        if isinstance(json_data, bytes):
            json_data = json_data.decode('utf-8')
        version_info = _channels_from_github_releases(json.loads(json_data))
    except IOError as e:
        if hasattr(e, 'reason'):
            errormessage = '%s' % e.reason
        elif hasattr(e, 'code'):
            errormessage = 'error code: %s' % e.code
        else:
            errormessage = '%s' % e
    except Exception as e:
        errormessage = repr(e)
    else:
        latestVersion = None
        channels = version_info['B3']['channels']
        if channel not in (UPDATE_CHANNEL_STABLE, UPDATE_CHANNEL_BETA, UPDATE_CHANNEL_DEV):
            errormessage = "unknown channel '%s': expecting (%s)" % (
                channel, ', '.join((UPDATE_CHANNEL_STABLE, UPDATE_CHANNEL_BETA, UPDATE_CHANNEL_DEV)))
        elif channel not in channels:
            # no release published for this channel (yet): nothing to update to
            return None
        else:
            latestVersion = channels[channel]['latest-version']

        if not errormessage:
            try:
                latestUrl = version_info['B3']['channels'][channel]['url']
            except KeyError:
                latestUrl = "https://github.com/%s/releases" % B3_GITHUB_REPOSITORY

            not singleLine and sys.stdout.write('latest B3 %s version is %s\n' % (channel, latestVersion))
            _lver = B3version(latestVersion)
            _cver = B3version(currentVersion)
            if _cver < _lver:
                if singleLine:
                    message = 'update available (v%s : %s)' % (latestVersion, latestUrl)
                else:
                    message = """
                 _\\|/_
                 (o o)    {version:^21}
         +----oOO---OOo-----------------------+
         |                                    |
         |                                    |
         | A newer version of B3 is available |
         |                                    |
         | {url:^34} |
         |                                    |
         +------------------------------------+

        """.format(version=latestVersion, url=latestUrl)

    if errormessage and showErrormsg:
        return errormessage
    elif message:
        return message
    else:
        return None


class DBUpdate(object):
    """
    Console database update procedure.
    """
    def __init__(self, config=None):
        """
        Object constructor.
        :param config: The B3 configuration file path
        """
        if config:
            # use the specified configuration file
            config = b3.getAbsolutePath(config, True)
            if not os.path.isfile(config):
                console_exit('ERROR: configuration file not found (%s).\n%s' % (config, b3.config_help()))
        else:
            # search a configuration file
            for p in ('b3.%s', 'conf/b3.%s', 'b3/conf/b3.%s',
                      os.path.join(HOMEDIR, 'b3.%s'), os.path.join(HOMEDIR, 'conf', 'b3.%s'),
                      os.path.join(HOMEDIR, 'b3', 'conf', 'b3.%s'), '@b3/conf/b3.%s'):
                for e in ('ini', 'cfg', 'xml'):
                    path = b3.getAbsolutePath(p % e, True)
                    if os.path.isfile(path):
                        print("Using configuration file: %s" % path)
                        config = path
                        sleep(3)
                        break

            if not config:
                console_exit('ERROR: could not find any valid configuration file.\n%s' % b3.config_help())
        try:
            self.config = b3.config.MainConfig(b3.config.load(config))
            if self.config.analyze():
                raise b3.config.ConfigFileNotValid
        except b3.config.ConfigFileNotValid:
            console_exit('ERROR: configuration file not valid (%s): edit it to fix the problem.\n%s' % (
                config, b3.config_help()))

    def run(self):
        """
        Run the DB update
        """
        clearscreen()
        print("""
                        _\\|/_
                        (o o)    {:>32}
                +----oOO---OOo----------------------------------+
                |                                               |
                |             UPDATING B3 DATABASE              |
                |                                               |
                +-----------------------------------------------+

        """.format('B3 : %s' % b3.__version__))

        input("press any key to start the update...")

        def _update_database(storage, update_version):
            """
            Update a B3 database.
            :param storage: the initialized storage module
            :param update_version: the update version
            """
            if B3version(b3.__version__) >= update_version:
                sql = b3.getAbsolutePath('@b3/sql/%s/b3-update-%s.sql' % (storage.protocol, update_version))
                if os.path.isfile(sql):
                    try:
                        print('>>> updating database to version %s' % update_version)
                        sleep(.5)
                        storage.queryFromFile(sql)
                    except Exception as err:
                        print('WARNING: could not update database properly: %s' % err)
                        sleep(3)

        dsn = self.config.get('b3', 'database')
        dsndict = splitDSN(dsn)
        database = getStorage(dsn, dsndict, StubParser())

        _update_database(database, '1.3.0')
        _update_database(database, '1.6.0')
        _update_database(database, '1.7.0')
        _update_database(database, '1.8.1')
        _update_database(database, '1.9.0')
        _update_database(database, '1.10.0')

        console_exit('B3 database update completed!')


from b3 import HOMEDIR
from b3.functions import console_exit, splitDSN, clearscreen
from b3.parser import StubParser
from b3.storage import getStorage