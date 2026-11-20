#!/bin/bash
# Each plugin's tests run in their own process: several parsers monkey-patch b3.clients classes when they start, and
# that would leak into the tests of unrelated plugins if everything ran in a single interpreter.
set -ev
for d in tests/plugins/*/; do
    case "$(basename "$d")" in fakeplugins|__pycache__) continue ;; esac
    python -m pytest -rsx "$d"
done
