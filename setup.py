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

__author__ = 'ThorN, xlr8or, courgette, Fenix'
__version__ = '4.0'

import os
import shutil
import setuptools

from setuptools import setup
from setuptools.command.egg_info import egg_info as orig_egg_info

# set by scripts/set_version.py (the release workflow sets it from the git tag)
b3_version = '2.0.2dev'

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))  # directory where this file is in
DIST_DIR = os.path.join(PROJECT_DIR, 'dist')  # directory where all the final builds will be found
BUILD_DIR = os.path.join(PROJECT_DIR, 'build')  # directory where all work will be done


class CleanCommand(setuptools.Command):
    """Custom clean command to tidy up the project root."""
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if os.path.isdir(BUILD_DIR):
            shutil.rmtree(BUILD_DIR)
        _egg_info_dir = os.path.join(PROJECT_DIR, 'b3.egg-info')
        if os.path.isdir(_egg_info_dir):
            shutil.rmtree(_egg_info_dir)


class my_egg_info(orig_egg_info):
    """
    Override egg_info command to copy the b3.egg-info/PKG-INFO file into the b3 directory
    """

    def run(self):
        write_commit_file()
        orig_egg_info.run(self)
        shutil.copy('b3.egg-info/PKG-INFO', 'b3/PKG-INFO')


def write_commit_file():
    """
    Record the git commit being built in b3/COMMIT, so `b3 --version` names it in an installed copy too
    (B3_COMMIT in the environment wins, for builds from a tree without .git).
    """
    import re
    import subprocess
    commit = os.environ.get('B3_COMMIT', '').strip().lower()
    if not commit and os.path.isdir(os.path.join(PROJECT_DIR, '.git')):
        try:
            commit = subprocess.check_output(['git', '-C', PROJECT_DIR, 'rev-parse', 'HEAD'],
                                             stderr=subprocess.DEVNULL, timeout=10).decode('ascii').strip()
        except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
            commit = ''
    if re.fullmatch(r'[0-9a-f]{7,40}', commit):
        with open(os.path.join(PROJECT_DIR, 'b3', 'COMMIT'), 'w', encoding='ascii') as f:
            f.write(commit + '\n')


cmdclass = {
    'egg_info': my_egg_info,
    'clean': CleanCommand,
}


########################################################################################################################
#                                                                                                                      #
#   SETUP                                                                                                              #
#                                                                                                                      #
########################################################################################################################

setup(
    cmdclass=cmdclass,
    name="b3",
    version=b3_version,
    author='Michael Thornton (ThorN), Tim ter Laak (ttlogic), Mark Weirath (xlr8or), Thomas Leveil (Courgette), Daniele Pantaleone (Fenix)',
    author_email="info@bigbrotherbot.net",
    description="BigBrotherBot (B3) is a cross-platform, cross-game game administration bot. "
                "Features in-game administration of game servers, multiple user access levels, and database storage. "
                "Currently include parsers for Altitude, Arma II, Arma III, Battlefield 3, Battlefield 4, Battlefield "
                "Bad Company 2, Battlefield Hardline, Chivalry Medieval Warfare, Call of Duty 1 to 8, Counter-Strike: "
                "Global Offensive, Ennemy Territory, Ennemy Territory Pro, Insurgency,  Urban Terror (ioUrT 4.1 and "
                "4.2), Medal of Honor 2010, Medal of Honor Warfighter, Open Arena, Red Orchestra 2, Smokin' Guns, "
                "Soldier of Fortune 2, World of Padman.",
    long_description="Big Brother Bot B3 is a complete and total server administration package for online games. "
                     "B3 is designed primarily to keep your server free from the derelicts of online gaming, but offers "
                     "more, much more. With the stock configuration files, B3 will will keep your server free from "
                     "offensive language, and team killers alike. A completely automated and customizable warning "
                     "system will warn the offending players that this type of behavior is not allowed on your server, "
                     "and ultimately kick, and or ban them for a predetermined time limit. B3 was designed to be easily "
                     "ported to other online games. Currently, B3 is in production for the Call of Duty series, "
                     "Urban Terror (ioUrT), etpro, World of Padman and Smokin' Guns since these games are based on "
                     "the Quake III Arena engine, conversion to any game using the engine should be easy. Plugins "
                     "provide much of the functionality for B3. These plugins can easily be configured. An SDK will "
                     "be provided to make your own plugins.",
    license="GPL-2.0-or-later",
    url="http://www.bigbrotherbot.net",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: System :: Logging',
        'Topic :: Utilities'
    ],
    python_requires='>=3.9',
    install_requires=[
        'pymysql>=1.0',
        'python-dateutil>=2.8',
        'feedparser>=6.0',
        'requests>=2.25',
        # offline country lookups in .mmdb databases (geolocation plugin): MaxMind's own reader, Apache-2.0
        'maxminddb>=2.6',
        # asyncore was removed from the standard library in Python 3.12
        'pyasyncore>=1.0; python_version >= "3.12"',
    ],
    packages=setuptools.find_packages(),
    # every data file B3 and its plugins read at runtime (sql scripts, sample configs, the bundled GeoIP database,
    # word lists...): the old one-level patterns left out everything below b3/plugins/<plugin>/
    package_data={'': [
        'PKG-INFO',
        'conf/**/*',
        'docs/*.*',
        'extplugins/**/*',
        'lib/**/*',
        'plugins/**/*',
        'sql/**/*',
        'tools/**/*',
    ]},
    exclude_package_data={'': ['*.pyc', '*.pyo', '__pycache__']},
    entry_points={
        'console_scripts': [
            'b3_run = b3.run:main',
        ]
    },
    options={
        'sdist': {
            'dist_dir': DIST_DIR,
        },
        'bdist_egg': {
            'dist_dir': DIST_DIR,
        },
    },
)

