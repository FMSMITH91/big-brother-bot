#!/bin/bash
set -ev
# --cov-fail-under=0: core alone covers about a third of b3; the coverage floor (.coveragerc) applies to the
# combined core + plugins measurement of the coverage job
python -m pytest -rsx tests/core --cov=b3 --cov-report=term-missing --cov-config=.coveragerc --cov-fail-under=0
