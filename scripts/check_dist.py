#!/usr/bin/env python3
"""
Check a built B3 wheel: every file tracked under b3/ (code and the data files B3 reads at runtime: sql scripts,
sample configs, the bundled GeoIP database...) must be in it, and no compiled file.

Usage: python scripts/check_dist.py dist/b3-*.whl
"""
import subprocess
import sys
import zipfile

# documentation sources, not needed to run B3
IGNORED_PREFIXES = ('b3/docs/user_documentation/',)


def missing_files(wheel_path, tracked):
    names = set(zipfile.ZipFile(wheel_path).namelist())
    return [f for f in tracked if f not in names and not f.startswith(IGNORED_PREFIXES)]


def compiled_files(wheel_path):
    return [n for n in zipfile.ZipFile(wheel_path).namelist() if n.endswith(('.pyc', '.pyo')) or '__pycache__' in n]


def main(wheel_path):
    tracked = subprocess.run(['git', 'ls-files', 'b3'], capture_output=True, text=True, check=True).stdout.split()
    missing = missing_files(wheel_path, tracked)
    compiled = compiled_files(wheel_path)
    for name in missing:
        print('missing from the wheel: %s' % name)
    for name in compiled:
        print('compiled file in the wheel: %s' % name)
    if missing or compiled:
        raise SystemExit(1)
    print('%s: all %s tracked b3 files present' % (wheel_path, len(tracked)))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
