#!/usr/bin/env bash
# validate-sast.sh - regression gate for the external SAST ingest backend.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/validate-sast.py
