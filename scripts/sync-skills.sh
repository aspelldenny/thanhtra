#!/usr/bin/env bash
# sync-skills.sh — copy shared content (rules/, references/, scripts/, workflows/small-review.md)
# từ canonical Claude skill sang Codex và Antigravity variants.
#
# CHẠY MỖI KHI sửa rule hoặc reference ở canonical.
#
# KHÔNG sync: SKILL.md, workflows/large-review.md / large-review-sequential.md
# (các file này khác nhau giữa 3 platform).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANONICAL="$ROOT/skills/thanhtra"

if [ ! -d "$CANONICAL" ]; then
  echo "❌ Canonical skill not found at $CANONICAL"
  exit 1
fi

# Verify rsync available
if ! command -v rsync >/dev/null 2>&1; then
  echo "❌ rsync not found. Install rsync first (macOS: brew install rsync)."
  exit 1
fi

targets=(
  "$ROOT/skills/codex/thanhtra"
  "$ROOT/skills/antigravity/thanhtra"
)

for target in "${targets[@]}"; do
  echo "→ Syncing to $target"
  mkdir -p "$target/rules" "$target/references" "$target/scripts" "$target/workflows"

  # Sync rules/ (21 generic + language overlays) — identical across platforms
  rsync -a --delete "$CANONICAL/rules/" "$target/rules/"

  # Sync references/ — identical across platforms
  rsync -a --delete "$CANONICAL/references/" "$target/references/"

  # Sync scripts/ — deterministic evidence collectors, identical across platforms
  rsync -a --delete --exclude '__pycache__/' --exclude '*.pyc' "$CANONICAL/scripts/" "$target/scripts/"

  # Sync small-review.md only (large-review variant differs per platform)
  cp "$CANONICAL/workflows/small-review.md" "$target/workflows/small-review.md"

  echo "  ✓ rules/ ($(find "$target/rules" -name '*.md' | wc -l | xargs) files)"
  echo "  ✓ references/ ($(find "$target/references" -name '*.md' | wc -l | xargs) files)"
  echo "  ✓ scripts/ ($(find "$target/scripts" -type f ! -name '*.pyc' | wc -l | xargs) files)"
  echo "  ✓ workflows/small-review.md"
done

echo ""
echo "✅ Sync complete. Codex + Antigravity variants now match canonical."
echo ""
echo "Reminder: SKILL.md và workflows/large-review-sequential.md là platform-specific,"
echo "chỉnh sửa thủ công từng file trong skills/codex/ và skills/antigravity/."
