#!/bin/bash
set -ev
python -m pytest tests/core --cov=b3 --cov-report=term-missing --cov-config=.coveragerc
