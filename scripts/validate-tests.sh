#!/usr/bin/env bash
# validate-tests.sh — run the stdlib unittest suite (zero dependencies).
# Tests the actual logic of prescan / triage / sarif / trust, not just structure.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m unittest discover -s tests -p 'test_*.py' -t "$ROOT"
