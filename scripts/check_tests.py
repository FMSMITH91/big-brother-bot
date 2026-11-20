#!/usr/bin/env python3
"""
Fail when a test cannot fail: a test function whose body is only `pass` (or a docstring) passes without testing
anything, and inflates the passed count. Skip it explicitly (@unittest.skip("reason")) or write it.

Usage: python scripts/check_tests.py [tests]
"""
import ast
import pathlib
import sys


def empty_tests(root):
    found = []
    for path in sorted(pathlib.Path(root).rglob('test_*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'), str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith('test'):
                continue
            skipped = any('skip' in ast.unparse(d) for d in node.decorator_list)
            body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
            if not skipped and all(isinstance(b, ast.Pass) for b in body):
                found.append('%s:%s %s' % (path, node.lineno, node.name))
    return found


if __name__ == '__main__':
    problems = empty_tests(sys.argv[1] if len(sys.argv) > 1 else 'tests')
    for p in problems:
        print('empty test (passes without testing anything): %s' % p)
    print('%s problem(s) found' % len(problems))
    sys.exit(1 if problems else 0)
