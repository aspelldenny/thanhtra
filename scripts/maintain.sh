#!/usr/bin/env bash
# maintain.sh - one-command local maintenance gate for Thanh Tra.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Sync shared skill content"
./scripts/sync-skills.sh

echo ""
echo "==> Validate skill structure"
./scripts/validate-skill.sh

echo ""
echo "==> Validate deterministic pre-scan"
./scripts/validate-pre-scan.sh

echo ""
echo "==> Validate regression fixtures"
./scripts/validate-fixtures.sh

echo ""
echo "==> Validate SARIF emitter"
./scripts/validate-sarif.sh

echo ""
echo "==> Validate SAST ingest"
./scripts/validate-sast.sh

echo ""
echo "==> Trust gate (anti agent-hijack)"
./scripts/validate-trust.sh

echo ""
echo "==> Verify install plan"
./scripts/install.sh --dry-run

echo ""
echo "Maintenance gate passed."
