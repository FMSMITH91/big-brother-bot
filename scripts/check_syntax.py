#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check every Python file of the project:
  - it compiles without any warning (SyntaxWarning: invalid escape sequences, 'is' with a literal,
    'return' in 'finally'...), and
  - it parses with the oldest supported Python grammar (3.9). Newer interpreters accept some syntax that
    older ones reject, e.g. Python 3.14 accepts 'except A, B:' (and gives it a different meaning).
Exit status is 1 when a problem is found.
"""

import ast
import pathlib
import sys
import warnings

OLDEST_PYTHON = (3, 9)
SKIP_DIRS = {'.venv', 'venv', '.git', 'build', 'dist', '__pycache__'}


def main(root):
    problems = []
    for path in sorted(pathlib.Path(root).rglob('*.py')):
        if SKIP_DIRS.intersection(path.parts):
            continue
        source = path.read_text(encoding='utf-8')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            try:
                compile(source, str(path), 'exec')
            except SyntaxError as e:
                problems.append('%s:%s: %s' % (path, e.lineno, e.msg))
                continue
        for w in caught:
            problems.append('%s:%s: %s' % (path, w.lineno, w.message))
        try:
            ast.parse(source, str(path), feature_version=OLDEST_PYTHON)
        except SyntaxError as e:
            problems.append('%s:%s: not valid Python %s.%s syntax: %s' % ((path, e.lineno) + OLDEST_PYTHON + (e.msg,)))
    for problem in problems:
        print(problem)
    print('%s problem(s) found' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else '.'))
