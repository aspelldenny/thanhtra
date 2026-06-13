#!/usr/bin/env bash
# validate-version.sh — guard against thanhtra.__version__ drifting BEHIND the
# latest release tag (the bug that shipped "1.2.0" through to v1.3.1).
# Allows == (released state) and > (preparing the next release); fails only when
# the package version is behind the newest tag. Skips gracefully when the
# checkout has no tags (e.g. a shallow CI clone).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ver="$(python3 -c 'import thanhtra; print(thanhtra.__version__)')"
tag="$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || true)"

if [ -z "$tag" ]; then
  echo "OK: __version__=$ver (no release tag in this checkout to compare against)"
  exit 0
fi

lowest="$(printf '%s\n%s\n' "$ver" "$tag" | sort -V | head -1)"
if [ "$ver" != "$tag" ] && [ "$lowest" = "$ver" ]; then
  echo "FAIL: __version__=$ver is behind latest tag v$tag — bump thanhtra/__init__.py" >&2
  exit 1
fi

echo "OK: __version__=$ver matches or leads latest tag v$tag"
