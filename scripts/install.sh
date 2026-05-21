#!/usr/bin/env bash
# install.sh — cài skill vbs-scan-security cho mọi platform CLI có trên máy.
#
# Detect các binary có sẵn trong PATH:
#   - claude       → ~/.claude/skills/vbs-scan-security
#   - codex        → ~/.agents/skills/vbs-scan-security
#   - antigravity  → ~/.gemini/antigravity/skills/vbs-scan-security
#
# Mặc định dùng symlink (đổi rule canonical → live update). Có flag --copy để copy thay symlink.
#
# Usage:
#   ./scripts/install.sh                  # symlink mode
#   ./scripts/install.sh --copy           # copy mode
#   ./scripts/install.sh --only=codex     # chỉ cài cho Codex
#   ./scripts/install.sh --dry-run        # in plan, không chạy

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="symlink"
ONLY=""
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --copy)     MODE="copy" ;;
    --symlink)  MODE="symlink" ;;
    --only=*)   ONLY="${arg#--only=}" ;;
    --dry-run)  DRY_RUN=1 ;;
    -h|--help)
      grep -E '^# ' "$0" | sed 's/^# //'
      exit 0
      ;;
    *) echo "Unknown arg: $arg"; exit 1 ;;
  esac
done

# Map: platform-name|binary-name|source-folder|target-dir
platforms=(
  "Claude Code|claude|$ROOT/skills/vbs-scan-security|$HOME/.claude/skills/vbs-scan-security"
  "OpenAI Codex|codex|$ROOT/skills/codex/vbs-scan-security|$HOME/.agents/skills/vbs-scan-security"
  "Google Antigravity|antigravity|$ROOT/skills/antigravity/vbs-scan-security|$HOME/.gemini/antigravity/skills/vbs-scan-security"
)

installed=0
skipped=0

for entry in "${platforms[@]}"; do
  IFS='|' read -r name binary source target <<<"$entry"
  short=$(echo "$name" | tr '[:upper:] ' '[:lower:]_')

  # Filter by --only
  if [ -n "$ONLY" ] && [[ "$short" != *"$ONLY"* ]]; then
    continue
  fi

  echo ""
  echo "─── $name ───"

  # Source must exist
  if [ ! -d "$source" ]; then
    echo "  ⏭  Source folder missing: $source"
    skipped=$((skipped+1))
    continue
  fi

  # Binary must be in PATH (unless --only forces install regardless)
  if [ -z "$ONLY" ] && ! command -v "$binary" >/dev/null 2>&1; then
    echo "  ⏭  Binary '$binary' not in PATH — skipping. (Use --only=$short to force.)"
    skipped=$((skipped+1))
    continue
  fi

  echo "  Source: $source"
  echo "  Target: $target"
  echo "  Mode:   $MODE"

  if [ $DRY_RUN -eq 1 ]; then
    echo "  [dry-run] would install"
    continue
  fi

  # Handle existing target
  if [ -L "$target" ]; then
    current=$(readlink "$target")
    if [ "$current" = "$source" ]; then
      echo "  ⏭  Already symlinked to correct source — skipping"
      skipped=$((skipped+1))
      continue
    fi
    # Symlink trỏ tới target khác → move ra ngoài skill dir (tránh Claude Code load thành skill duplicate)
    backup_dir="$HOME/.claude/skills-backups"
    mkdir -p "$backup_dir"
    backup="$backup_dir/$(basename "$target").backup-$(date +%Y%m%d-%H%M%S)"
    echo "  ⚠  Existing symlink points elsewhere — moving to $backup"
    mv "$target" "$backup"
  elif [ -e "$target" ]; then
    # Folder/file thật → backup ra ngoài skill dir
    backup_dir="$HOME/.claude/skills-backups"
    mkdir -p "$backup_dir"
    backup="$backup_dir/$(basename "$target").backup-$(date +%Y%m%d-%H%M%S)"
    echo "  ⚠  Existing folder found — moving to $backup"
    mv "$target" "$backup"
  fi

  # Ensure parent dir exists
  mkdir -p "$(dirname "$target")"

  # Install
  if [ "$MODE" = "symlink" ]; then
    ln -s "$source" "$target"
    echo "  ✅ Symlinked"
  else
    cp -R "$source" "$target"
    echo "  ✅ Copied"
  fi

  installed=$((installed+1))
done

echo ""
echo "═══════════════════════════════════════"
echo "  Installed: $installed"
echo "  Skipped:   $skipped"
echo "═══════════════════════════════════════"

if [ $installed -gt 0 ]; then
  echo ""
  echo "Test ngay:"
  command -v claude >/dev/null 2>&1       && echo "  - Claude:      claude → gõ /vbs-scan-security"
  command -v codex >/dev/null 2>&1        && echo "  - Codex:       codex → gõ \$vbs-scan-security  (hoặc /skills)"
  command -v antigravity >/dev/null 2>&1  && echo "  - Antigravity: mở Antigravity, nói 'scan security' trong Agent Manager"
fi
