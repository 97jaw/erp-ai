#!/usr/bin/env bash
set -euo pipefail
python -m pytest tests/quality/ tests/test_quality_formatting.py tests/test_quality_validation.py
python tools/lint_responses.py
