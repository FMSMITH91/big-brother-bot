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

import importlib.util
import os
import shutil
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


set_version = load('scripts/set_version.py', 'set_version')
check_dist = load('scripts/check_dist.py', 'check_dist')
build_installer = load('installer/windows/build_installer.py', 'build_installer')


class Test_set_version(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.mkdir(os.path.join(self.root, 'b3'))
        shutil.copy(os.path.join(ROOT, 'setup.py'), self.root)
        shutil.copy(os.path.join(ROOT, 'b3', '__init__.py'), os.path.join(self.root, 'b3'))

    def read(self, name):
        with open(os.path.join(self.root, name)) as f:
            return f.read()

    def test_sets_both_files_from_a_tag(self):
        self.assertEqual('2.0.0b1', set_version.set_version('v2.0.0b1', self.root))
        self.assertIn("\nb3_version = '2.0.0b1'\n", self.read('setup.py'))
        self.assertIn("\n__version__ = '2.0.0b1'\n", self.read(os.path.join('b3', '__init__.py')))
        # the setup script's own version is left alone
        self.assertIn("\n__version__ = '4.0'\n", self.read('setup.py'))

    def test_versions_the_update_check_understands(self):
        from b3.update import B3version
        for version in ('2.0.0', '2.0', '2.0.0a1', '2.0.0b2', '1.12dev7'):
            self.assertEqual(version, set_version.set_version(version, self.root))
            B3version(version)  # raises ValueError if the update check could not parse it

    def test_rejects_other_version_numbers(self):
        for version in ('2.0.0rc1', '2', 'latest', '2.0.0-beta', "2.0'; rm"):
            self.assertRaises(ValueError, set_version.set_version, version, self.root)


class Test_check_dist(unittest.TestCase):

    def test_reports_missing_and_compiled_files(self):
        path = os.path.join(tempfile.mkdtemp(), 'b3.whl')
        self.addCleanup(shutil.rmtree, os.path.dirname(path))
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('b3/__init__.py', '')
            z.writestr('b3/__pycache__/x.cpython-314.pyc', '')
        tracked = ['b3/__init__.py', 'b3/plugins/geolocation/lib/geoip/db/GeoIP.dat', 'b3/docs/user_documentation/x.rst']
        self.assertEqual(['b3/plugins/geolocation/lib/geoip/db/GeoIP.dat'], check_dist.missing_files(path, tracked))
        self.assertEqual(['b3/__pycache__/x.cpython-314.pyc'], check_dist.compiled_files(path))


class Test_windows_installer(unittest.TestCase):

    def test_embedded_python_loads_site_packages(self):
        # the ._pth file shipped with the embeddable Python (3.14) leaves "import site" commented out
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with open(os.path.join(folder, 'python314._pth'), 'w', newline='\r\n') as f:
            f.write('python314.zip\n.\n\n# Uncomment to run site.main() automatically\n#import site\n')
        build_installer.enable_site_packages(folder)
        with open(os.path.join(folder, 'python314._pth')) as f:
            lines = f.read().splitlines()
        self.assertEqual(['python314.zip', '.', 'Lib\\site-packages', '', '# Uncomment to run site.main() automatically',
                          'import site'], lines)

    def test_embed_version_matches_the_ci_python(self):
        with open(os.path.join(ROOT, '.github', 'workflows', 'release.yml')) as f:
            workflow = f.read()
        minor = '.'.join(build_installer.EMBED_VERSION.split('.')[:2])
        self.assertIn('python-version: "%s"' % minor, workflow.split('windows-installer:')[1])

    def write_wheel(self, folder, name, init):
        with zipfile.ZipFile(os.path.join(folder, name), 'w') as z:
            z.writestr('b3/__init__.py', init)

    def test_wheel_and_version_found_in_dist(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        open(os.path.join(folder, 'b3-2.0.0b1.tar.gz'), 'w').close()
        self.write_wheel(folder, 'b3-2.0.0b1-py3-none-any.whl', "import os\n__version__ = '2.0.0b1'\n")
        self.assertEqual((os.path.join(folder, 'b3-2.0.0b1-py3-none-any.whl'), '2.0.0b1'),
                         build_installer.find_wheel(folder))

    def test_refuses_missing_or_ambiguous_wheel_and_odd_versions(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        self.assertRaises(SystemExit, build_installer.find_wheel, folder)
        self.write_wheel(folder, 'b3-2.0.0-py3-none-any.whl', "__version__ = '2.0.0 /DFOO=1'\n")
        self.assertRaises(SystemExit, build_installer.find_wheel, folder)
        self.write_wheel(folder, 'b3-2.0.1-py3-none-any.whl', "__version__ = '2.0.1'\n")
        self.assertRaises(SystemExit, build_installer.find_wheel, folder)

    def test_inno_setup_script_uses_the_staged_files(self):
        with open(os.path.join(ROOT, 'installer', 'innosetup', 'b3.iss')) as f:
            iss = f.read()
        self.assertIn('OutputBaseFilename=b3-{#B3_VERSION}-win64-setup', iss)
        for name in ('python\\*', 'b3.cmd', 'run-b3.cmd', 'readme.txt', 'license.txt', 'conf\\*', 'extplugins\\*'):
            self.assertIn('{#B3_STAGE_DIR}\\' + name, iss)
        # shortcuts keep the window open when B3 stops (it used to vanish on a configuration error)
        self.assertNotIn('Filename: "{app}\\b3.cmd"', iss)
        self.assertIn('Filename: "{app}\\run-b3.cmd"', iss)

    def test_console_launcher_waits(self):
        self.assertIn('call "%~dp0b3.cmd" %*', build_installer.CONSOLE_LAUNCHER)
        self.assertIn('pause', build_installer.CONSOLE_LAUNCHER)
        self.assertNotIn('pause', build_installer.LAUNCHER)


if __name__ == '__main__':
    unittest.main()
