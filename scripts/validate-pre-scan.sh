#!/usr/bin/env bash
# validate-pre-scan.sh - regression gate for deterministic evidence collection.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/validate-pre-scan.py
