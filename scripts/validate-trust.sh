#!/usr/bin/env bash
# validate-trust.sh - gate: this repo must never carry agent-targeting payloads.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/validate-trust.py "$@"
