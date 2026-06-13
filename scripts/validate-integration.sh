#!/usr/bin/env bash
# validate-integration.sh — score Thanh Tra's deterministic pre-scan against an
# EXTERNAL labelled corpus (Bandit's examples/). This is the objective recall
# yardstick our own fixtures cannot be: an independent third party wrote both
# the vulnerable code AND its labels.
#
# OPT-IN. Not part of maintain.sh: it needs network (clones Bandit once) and is
# a measurement, not a fast structural gate. Run it by hand, or wire a separate
# nightly CI job.
#
# DISCIPLINE: do NOT tune hotspot patterns to raise this score — that turns the
# yardstick into another fixture (teaching to the test). Improve patterns from
# first principles; measure on a HELD-OUT corpus.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BANDIT_TAG="1.8.6"
CACHE="$ROOT/.integration-cache/bandit"

if [ ! -d "$CACHE/examples" ]; then
  echo "Cloning Bandit @ $BANDIT_TAG (one-time, into .integration-cache/)…"
  rm -rf "$CACHE"
  git clone --quiet --branch "$BANDIT_TAG" --depth 1 \
    https://github.com/PyCQA/bandit.git "$CACHE"
fi

EV="$(mktemp)"
trap 'rm -f "$EV"' EXIT
./bin/thanhtra prescan --root "$CACHE/examples" --no-audit > "$EV" 2>/dev/null
python3 scripts/integration_score.py "$EV"
