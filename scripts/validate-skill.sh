#!/usr/bin/env bash
# validate-skill.sh - structural checks for Thanh Tra skill maintenance.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANONICAL="$ROOT/skills/thanhtra"
CODEX="$ROOT/skills/codex/thanhtra"
ANTIGRAVITY="$ROOT/skills/antigravity/thanhtra"

failures=0

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  failures=$((failures + 1))
}

pass() {
  printf 'OK: %s\n' "$1"
}

require_dir() {
  local dir="$1"
  local label="$2"
  if [ -d "$dir" ]; then
    pass "$label exists"
  else
    fail "$label missing: $dir"
  fi
}

extract_frontmatter_value() {
  local key="$1"
  local file="$2"
  awk -F': *' -v key="$key" '
    NR == 1 && $0 != "---" { exit }
    NR > 1 && $0 == "---" { exit }
    $1 == key { print $2; exit }
  ' "$file"
}

extract_i18n_keys() {
  local file="$1"
  sed -n 's/^| `\([^`][^`]*\)` |.*$/\1/p' "$file" | sort -u
}

check_generic_rules() {
  local rule_dir="$CANONICAL/rules/generic"
  local count
  count="$(find "$rule_dir" -maxdepth 1 -type f -name '[0-9][0-9]-*.md' | wc -l | tr -d ' ')"

  if [ "$count" = "24" ]; then
    pass "canonical generic rule count is 24"
  else
    fail "canonical generic rule count is $count, expected 24"
  fi

  local tmp_ids
  tmp_ids="$(mktemp)"

  local expected=1
  local file base prefix id severity applies
  while IFS= read -r file; do
    base="$(basename "$file")"
    prefix="${base%%-*}"

    if [ "$prefix" != "$(printf '%02d' "$expected")" ]; then
      fail "generic rule order mismatch at $base, expected prefix $(printf '%02d' "$expected")"
    fi

    id="$(extract_frontmatter_value id "$file")"
    severity="$(extract_frontmatter_value severity_max "$file")"
    applies="$(extract_frontmatter_value applies_to "$file")"

    [ -n "$id" ] || fail "$base missing frontmatter id"
    [ -n "$severity" ] || fail "$base missing frontmatter severity_max"
    [ -n "$applies" ] || fail "$base missing frontmatter applies_to"

    case "$severity" in
      CRITICAL|HIGH|MEDIUM|LOW) ;;
      *) fail "$base has invalid severity_max: ${severity:-<empty>}" ;;
    esac

    if [ "$applies" != "all" ]; then
      fail "$base applies_to is $applies, expected all"
    fi

    printf '%s\n' "$id" >> "$tmp_ids"
    expected=$((expected + 1))
  done < <(find "$rule_dir" -maxdepth 1 -type f -name '[0-9][0-9]-*.md' | sort)

  local unique_count
  unique_count="$(sort -u "$tmp_ids" | wc -l | tr -d ' ')"
  if [ "$unique_count" = "$count" ]; then
    pass "canonical generic rule IDs are unique"
  else
    fail "canonical generic rule IDs are not unique"
  fi

  rm -f "$tmp_ids"
}

check_language_overlays() {
  local overlay_root="$CANONICAL/rules/languages"
  local file base prefix generic_file id generic_id severity applies lang

  while IFS= read -r file; do
    base="$(basename "$file")"
    lang="$(basename "$(dirname "$file")")"
    prefix="${base%%-*}"
    generic_file="$(find "$CANONICAL/rules/generic" -maxdepth 1 -type f -name "${prefix}-*.md" | head -n 1)"

    if [ -z "$generic_file" ]; then
      fail "overlay $lang/$base has no matching generic rule prefix"
      continue
    fi

    id="$(extract_frontmatter_value id "$file")"
    generic_id="$(extract_frontmatter_value id "$generic_file")"
    severity="$(extract_frontmatter_value severity_max "$file")"
    applies="$(extract_frontmatter_value applies_to "$file")"

    [ "$id" = "$generic_id" ] || fail "overlay $lang/$base id $id does not match generic $generic_id"
    [ -n "$severity" ] || fail "overlay $lang/$base missing severity_max"
    [ "$applies" = "$lang" ] || fail "overlay $lang/$base applies_to is $applies, expected $lang"
  done < <(find "$overlay_root" -mindepth 2 -type f -name '[0-9][0-9]-*.md' | sort)

  pass "language overlays reference existing generic rules"
}

check_i18n_parity() {
  local vi="$CANONICAL/references/i18n/vi.md"
  local en="$CANONICAL/references/i18n/en.md"
  local vi_keys en_keys diff_out

  vi_keys="$(mktemp)"
  en_keys="$(mktemp)"
  extract_i18n_keys "$vi" > "$vi_keys"
  extract_i18n_keys "$en" > "$en_keys"

  if diff_out="$(diff -u "$vi_keys" "$en_keys")"; then
    pass "i18n vi/en keys match"
  else
    fail "i18n vi/en key mismatch"
    printf '%s\n' "$diff_out" >&2
  fi

  rm -f "$vi_keys" "$en_keys"
}

check_platform_sync() {
  local target="$1"
  local label="$2"
  local diff_out

  if diff_out="$(diff -qr "$CANONICAL/rules" "$target/rules")"; then
    pass "$label rules match canonical"
  else
    fail "$label rules differ from canonical"
    printf '%s\n' "$diff_out" >&2
  fi

  if diff_out="$(diff -qr "$CANONICAL/references" "$target/references")"; then
    pass "$label references match canonical"
  else
    fail "$label references differ from canonical"
    printf '%s\n' "$diff_out" >&2
  fi

  if diff_out="$(diff -qr "$CANONICAL/scripts" "$target/scripts")"; then
    pass "$label scripts match canonical"
  else
    fail "$label scripts differ from canonical"
    printf '%s\n' "$diff_out" >&2
  fi

  if cmp -s "$CANONICAL/workflows/small-review.md" "$target/workflows/small-review.md"; then
    pass "$label small-review workflow matches canonical"
  else
    fail "$label small-review workflow differs from canonical"
  fi

  [ -f "$target/SKILL.md" ] || fail "$label SKILL.md missing"
  [ -f "$target/workflows/large-review-sequential.md" ] || fail "$label sequential large workflow missing"
}

check_scripts() {
  local pre_scan="$CANONICAL/scripts/thanhtra-pre-scan.py"
  if [ -x "$pre_scan" ] || [ -f "$pre_scan" ]; then
    pass "pre-scan script exists"
  else
    fail "pre-scan script missing: $pre_scan"
    return
  fi

  if python3 - "$pre_scan" <<'PY'
import ast
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
PY
  then
    pass "pre-scan script compiles"
  else
    fail "pre-scan script does not compile"
  fi
}

check_docs_basics() {
  [ -f "$ROOT/README.md" ] || fail "README.md missing"
  [ -f "$ROOT/README.vi.md" ] || fail "README.vi.md missing"
  [ -f "$ROOT/LICENSE" ] || fail "LICENSE missing"
  pass "top-level docs are present"
}

main() {
  require_dir "$CANONICAL" "canonical skill"
  require_dir "$CODEX" "Codex skill variant"
  require_dir "$ANTIGRAVITY" "Antigravity skill variant"

  check_generic_rules
  check_language_overlays
  check_scripts
  check_i18n_parity
  check_platform_sync "$CODEX" "Codex"
  check_platform_sync "$ANTIGRAVITY" "Antigravity"
  check_docs_basics

  if [ "$failures" -eq 0 ]; then
    printf '\nValidation passed.\n'
    exit 0
  fi

  printf '\nValidation failed with %d issue(s).\n' "$failures" >&2
  exit 1
}

main "$@"
