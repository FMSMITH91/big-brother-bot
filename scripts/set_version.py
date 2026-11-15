#!/usr/bin/env python3
"""
Set the B3 version number everywhere it is written down (setup.py and b3/__init__.py).

Usage: python scripts/set_version.py 2.0.0b1

Accepts the B3 version scheme understood by the update check (b3/update.py): 1.2, 1.2.3, 1.2.3a1, 1.2.3b2, 1.2.3dev4.
A leading "v" (a git tag such as v2.0.0) is stripped.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_RE = re.compile(r'^\d+\.\d+(?:\.\d+)?(?:(?:a|b|dev)\d*)?$')
FILES = {
    'setup.py': re.compile(r"^(b3_version = ')[^']*(')$", re.MULTILINE),
    os.path.join('b3', '__init__.py'): re.compile(r"^(__version__ = ')[^']*(')$", re.MULTILINE),
}


def set_version(version, root=ROOT):
    if version[:1] in ('v', 'V'):
        version = version[1:]
    if not VERSION_RE.match(version):
        raise ValueError('not a B3 version number: %r (expected e.g. 2.0.0, 2.0.0b1)' % version)
    for name, pattern in FILES.items():
        path = os.path.join(root, name)
        with open(path, encoding='utf-8', newline='') as f:
            content = f.read()
        content, count = pattern.subn(lambda m: m.group(1) + version + m.group(2), content)
        if count != 1:
            raise RuntimeError('could not find the version line in %s' % path)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
    return version


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(set_version(sys.argv[1]))
