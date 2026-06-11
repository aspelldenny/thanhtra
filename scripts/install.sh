#!/usr/bin/env bash
# install.sh — cài skill thanhtra cho mọi platform có trên máy.
#
# Detection (auto):
#   - Claude Code        → binary `claude`               → ~/.claude/skills/thanhtra
#   - OpenAI Codex CLI   → binary `codex`                → ~/.agents/skills/thanhtra
#   - Google Antigravity → app /Applications/Antigravity.app
#                          HOẶC binary `agy`             → ~/.gemini/antigravity/skills/thanhtra
#
# Antigravity là IDE (không phải CLI). Detection check app folder hoặc CLI tool `agy`
# (user tự install qua menu trong Antigravity IDE).
#
# Mặc định dùng symlink (sửa rule canonical → live update). Có flag --copy để copy thay symlink.
#
# Ngoài skill, script cũng cài Thanh Tra CLI (bin/thanhtra) vào ~/.local/bin
# để agent ở bất kỳ repo nào cũng gọi được `thanhtra prescan` / `thanhtra scan`.
# CLI luôn cài dạng symlink (kể cả --copy) vì launcher cần package thanhtra/ trong repo.
#
# Usage:
#   ./scripts/install.sh                       # auto-detect, symlink mode
#   ./scripts/install.sh --copy                # copy mode (chỉ áp dụng cho skill)
#   ./scripts/install.sh --only=codex          # chỉ cài cho 1 platform (force, bỏ qua detection)
#   ./scripts/install.sh --only=antigravity    # ép cài Antigravity (kể cả khi chưa cài app)
#   ./scripts/install.sh --all                 # cài cho cả 3 platform (bỏ qua detection)
#   ./scripts/install.sh --no-cli              # bỏ qua bước cài CLI
#   ./scripts/install.sh --dry-run             # in plan, không chạy

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="symlink"
ONLY=""
FORCE_ALL=0
DRY_RUN=0
INSTALL_CLI=1
for arg in "$@"; do
  case "$arg" in
    --copy)     MODE="copy" ;;
    --symlink)  MODE="symlink" ;;
    --only=*)   ONLY="${arg#--only=}" ;;
    --all)      FORCE_ALL=1 ;;
    --no-cli)   INSTALL_CLI=0 ;;
    --dry-run)  DRY_RUN=1 ;;
    -h|--help)
      grep -E '^# ' "$0" | sed 's/^# //'
      exit 0
      ;;
    *) echo "Unknown arg: $arg"; exit 1 ;;
  esac
done

# Detection cho từng platform. Return 0 nếu detected, 1 nếu không.
detect_claude()       { command -v claude >/dev/null 2>&1; }
detect_codex()        { command -v codex >/dev/null 2>&1; }
detect_antigravity()  {
  # macOS standard install
  [ -d "/Applications/Antigravity.app" ] && return 0
  # CLI tool agy (user tự install qua menu Antigravity IDE)
  command -v agy >/dev/null 2>&1 && return 0
  return 1
}

# Map: short-key|platform-name|detect-function|source-folder|target-dir
platforms=(
  "claude|Claude Code|detect_claude|$ROOT/skills/thanhtra|$HOME/.claude/skills/thanhtra"
  "codex|OpenAI Codex|detect_codex|$ROOT/skills/codex/thanhtra|$HOME/.agents/skills/thanhtra"
  "antigravity|Google Antigravity|detect_antigravity|$ROOT/skills/antigravity/thanhtra|$HOME/.gemini/antigravity/skills/thanhtra"
)

installed=0
skipped=0

for entry in "${platforms[@]}"; do
  IFS='|' read -r short name detect_fn source target <<<"$entry"

  # Filter by --only
  if [ -n "$ONLY" ] && [ "$short" != "$ONLY" ]; then
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

  # Detection (unless --only or --all forces install regardless)
  if [ -z "$ONLY" ] && [ $FORCE_ALL -eq 0 ]; then
    if ! $detect_fn; then
      echo "  ⏭  $name không detect được — skipping."
      echo "      Force install: --only=$short hoặc --all"
      skipped=$((skipped+1))
      continue
    fi
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
    backup_dir="$HOME/.thanhtra-install-backups"
    mkdir -p "$backup_dir"
    backup="$backup_dir/$(basename "$target").backup-$(date +%Y%m%d-%H%M%S)"
    echo "  ⚠  Existing symlink points elsewhere — moving to $backup"
    mv "$target" "$backup"
  elif [ -e "$target" ]; then
    backup_dir="$HOME/.thanhtra-install-backups"
    mkdir -p "$backup_dir"
    backup="$backup_dir/$(basename "$target").backup-$(date +%Y%m%d-%H%M%S)"
    echo "  ⚠  Existing folder found — moving to $backup"
    mv "$target" "$backup"
  fi

  # Ensure parent dir exists (Antigravity user mới chưa có ~/.gemini/antigravity/skills/)
  parent_dir=$(dirname "$target")
  if [ ! -d "$parent_dir" ]; then
    echo "  📁 Tạo parent dir: $parent_dir"
    mkdir -p "$parent_dir"
  fi

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

# ─── Thanh Tra CLI → ~/.local/bin (luôn symlink, launcher cần package thanhtra/ trong repo) ───
if [ $INSTALL_CLI -eq 1 ]; then
  echo ""
  echo "─── Thanh Tra CLI ───"
  cli_dir="$HOME/.local/bin"
  for cli_name in thanhtra; do
    cli_source="$ROOT/bin/$cli_name"
    cli_target="$cli_dir/$cli_name"
    if [ $DRY_RUN -eq 1 ]; then
      echo "  [dry-run] would symlink $cli_target → $cli_source"
      continue
    fi
    mkdir -p "$cli_dir"
    if [ -L "$cli_target" ] && [ "$(readlink "$cli_target")" = "$cli_source" ]; then
      echo "  ⏭  $cli_name already symlinked — skipping"
      continue
    fi
    if [ -e "$cli_target" ] || [ -L "$cli_target" ]; then
      backup_dir="$HOME/.thanhtra-install-backups"
      mkdir -p "$backup_dir"
      backup="$backup_dir/$cli_name.backup-$(date +%Y%m%d-%H%M%S)"
      echo "  ⚠  Existing $cli_target — moving to $backup"
      mv "$cli_target" "$backup"
    fi
    ln -s "$cli_source" "$cli_target"
    echo "  ✅ $cli_name → $cli_target"
  done
  case ":$PATH:" in
    *":$cli_dir:"*) ;;
    *)
      echo "  ⚠  $cli_dir chưa có trong PATH. Thêm vào shell profile:"
      echo "      export PATH=\"\$HOME/.local/bin:\$PATH\""
      ;;
  esac
fi

echo ""
echo "═══════════════════════════════════════"
echo "  Installed: $installed"
echo "  Skipped:   $skipped"
echo "═══════════════════════════════════════"

if [ $installed -gt 0 ]; then
  echo ""
  echo "Test ngay:"
  detect_claude       && echo "  - Claude:      claude → gõ /thanhtra"
  detect_codex        && echo "  - Codex:       codex → gõ \$thanhtra  (hoặc /skills)"
  detect_antigravity  && echo "  - Antigravity: mở Antigravity app, nói 'scan security' trong Agent Manager"
fi

if [ $skipped -gt 0 ] && [ -z "$ONLY" ] && [ $FORCE_ALL -eq 0 ]; then
  echo ""
  echo "💡 Để force cài cho platform chưa detect: ./scripts/install.sh --only=<claude|codex|antigravity>"
  echo "   Hoặc cài cho cả 3:                    ./scripts/install.sh --all"
fi
