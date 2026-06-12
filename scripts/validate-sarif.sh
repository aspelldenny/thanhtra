#!/usr/bin/env bash
# validate-sarif.sh - regression gate for the SARIF 2.1.0 emitter.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/validate-sarif.py
