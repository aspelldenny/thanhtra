#!/usr/bin/env bash
# validate-fixtures.sh - validate fixture metadata for Thanh Tra regression cases.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/scripts/validate-fixtures.py"
