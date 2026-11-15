#!/usr/bin/env python3
"""
Build the B3 Windows installer.

The installer ships the official embeddable Python from python.org with B3 (from its wheel) and its dependencies
installed into it, plus a b3.cmd launcher, packaged with Inno Setup 6. B3 loads its plugins from source files at
runtime, which a real Python handles exactly like on Linux (a frozen executable did not).

Run it on Windows with the same Python minor version as EMBED_VERSION (pip installs the dependencies, and builds
the pure-Python ones shipped as source only, for the running interpreter), after building the wheel into dist/:

    python -m build
    python installer/windows/build_installer.py

It takes no arguments: it installs the one B3 wheel found in dist/, reads the version from it, works in
build/windows and writes dist/b3-<version>-win64-setup.exe.

Inno Setup's ISCC.exe is looked up in ISCC_EXE, in PATH, then in its default install folders.
"""
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(ROOT, 'installer', 'assets_common')
ISS_SCRIPT = os.path.join(ROOT, 'installer', 'innosetup', 'b3.iss')

# official Windows embeddable package; the hash pins the exact file (a changed download fails the build)
EMBED_VERSION = '3.14.10'
EMBED_URL = 'https://www.python.org/ftp/python/%s/python-%s-embed-amd64.zip' % (EMBED_VERSION, EMBED_VERSION)
EMBED_SHA256 = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'

# optional dependencies worth shipping: PostgreSQL storage, the sftpytail plugin
EXTRA_PACKAGES = ['psycopg2-binary>=2.9', 'paramiko>=3.0']

# the B3 version scheme (scripts/set_version.py): 2.0.0, 2.0.0b1...
VERSION_RE = re.compile(r'^\d+\.\d+(?:\.\d+)?(?:(?:a|b|dev)\d*)?$')

LAUNCHER = '@echo off\r\nrem Run BigBrotherBot (B3): b3.cmd --help lists the options\r\n' \
           '"%~dp0python\\python.exe" -m b3.run %*\r\n'


def log(msg):
    print('>>> %s' % msg, flush=True)


def download_embedded_python(cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, os.path.basename(EMBED_URL))
    if not os.path.isfile(path):
        log('downloading %s' % EMBED_URL)
        with urllib.request.urlopen(EMBED_URL, timeout=120) as response, open(path + '.part', 'wb') as f:
            shutil.copyfileobj(response, f)
        os.replace(path + '.part', path)
    with open(path, 'rb') as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != EMBED_SHA256:
        raise SystemExit('%s: SHA-256 %s does not match the pinned %s' % (path, digest, EMBED_SHA256))
    return path


def enable_site_packages(python_dir):
    """
    The embeddable Python ignores site-packages until its ._pth file says otherwise.
    """
    pth = [n for n in os.listdir(python_dir) if n.endswith('._pth')]
    if len(pth) != 1:
        raise SystemExit('expected one ._pth file in %s, found %s' % (python_dir, pth))
    path = os.path.join(python_dir, pth[0])
    with open(path, encoding='utf-8') as f:
        lines = [line.rstrip('\r\n') for line in f]
    lines = ['import site' if line.strip() == '#import site' else line for line in lines]
    if 'Lib\\site-packages' not in lines:
        lines.insert(lines.index('.') + 1 if '.' in lines else len(lines), 'Lib\\site-packages')
    if 'import site' not in lines:
        lines.append('import site')
    with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(lines) + '\n')


def check_interpreter():
    if sys.platform != 'win32':
        raise SystemExit('run this on Windows: the dependencies are installed for the running interpreter')
    embed_minor = tuple(int(x) for x in EMBED_VERSION.split('.')[:2])
    if sys.version_info[:2] != embed_minor:
        raise SystemExit('run this with Python %s.%s (the embedded Python version), not %s.%s'
                         % (embed_minor + sys.version_info[:2]))


def stage(wheel, stage_dir, cache_dir):
    if os.path.isdir(stage_dir):
        shutil.rmtree(stage_dir)
    python_dir = os.path.join(stage_dir, 'python')
    log('extracting the embeddable Python %s' % EMBED_VERSION)
    with zipfile.ZipFile(download_embedded_python(cache_dir)) as z:
        z.extractall(python_dir)
    enable_site_packages(python_dir)

    site_packages = os.path.join(python_dir, 'Lib', 'site-packages')
    log('installing B3 and its dependencies into %s' % site_packages)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', '--no-compile', '--disable-pip-version-check',
                    '--target', site_packages, wheel] + EXTRA_PACKAGES, check=True)

    with open(os.path.join(stage_dir, 'b3.cmd'), 'w', newline='') as f:
        f.write(LAUNCHER)
    shutil.copy(os.path.join(ASSETS, 'b3.ico'), stage_dir)
    shutil.copy(os.path.join(ASSETS, 'b3-plugins-icon.ico'), stage_dir)
    shutil.copy(os.path.join(ASSETS, 'gpl-2.0.txt'), os.path.join(stage_dir, 'license.txt'))
    shutil.copy(os.path.join(ASSETS, 'readme-windows.txt'), os.path.join(stage_dir, 'readme.txt'))
    for name in ('conf', 'extplugins'):
        # sample configs and the folder for third party plugins, next to b3.cmd where users look for them
        shutil.copytree(os.path.join(site_packages, 'b3', name), os.path.join(stage_dir, name),
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    return stage_dir


def find_iscc():
    candidates = [os.environ.get('ISCC_EXE'), shutil.which('iscc'), shutil.which('ISCC')]
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'),
                 os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')):
        if base:
            candidates.append(os.path.join(base, 'Inno Setup 6', 'ISCC.exe'))
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    raise SystemExit('Inno Setup 6 compiler (ISCC.exe) not found: install Inno Setup 6 or set ISCC_EXE')


def compile_installer(stage_dir, version, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    log('compiling the installer with Inno Setup')
    subprocess.run([find_iscc(), '/Q', '/O' + os.path.abspath(out_dir), '/DB3_VERSION=' + version,
                    '/DB3_STAGE_DIR=' + os.path.abspath(stage_dir), ISS_SCRIPT], check=True)
    installer = os.path.join(out_dir, 'b3-%s-win64-setup.exe' % version)
    if not os.path.isfile(installer):
        raise SystemExit('Inno Setup did not produce %s' % installer)
    log('built %s' % installer)
    return installer


DIST_DIR = os.path.join(ROOT, 'dist')
BUILD_DIR = os.path.join(ROOT, 'build', 'windows')


def find_wheel(dist_dir=DIST_DIR):
    """
    Return the B3 wheel in dist/ and the B3 version written in it.
    """
    wheels = glob.glob(os.path.join(dist_dir, 'b3-*-py3-none-any.whl'))
    if len(wheels) != 1:
        raise SystemExit('expected one B3 wheel in %s, found %s: build it with python -m build' % (dist_dir, wheels))
    with zipfile.ZipFile(wheels[0]) as z:
        source = z.read('b3/__init__.py').decode('utf-8')
    match = re.search(r"^__version__ = '([^']+)'$", source, re.MULTILINE)
    if not match or not VERSION_RE.match(match.group(1)):
        raise SystemExit('could not read a B3 version number from %s' % wheels[0])
    return wheels[0], match.group(1)


def main():
    check_interpreter()
    wheel, version = find_wheel()
    log('building the installer of B3 %s from %s' % (version, wheel))
    stage_dir = stage(wheel, os.path.join(BUILD_DIR, 'stage'), os.path.join(BUILD_DIR, 'cache'))
    compile_installer(stage_dir, version, DIST_DIR)


if __name__ == '__main__':
    main()
