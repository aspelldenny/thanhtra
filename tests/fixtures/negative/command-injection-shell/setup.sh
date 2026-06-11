#!/usr/bin/env bash
# register-project: thêm project vào registry trong shell rc (đã sanitize)

register-project() {
  local path="$1"
  local name
  name=$(basename "$path")
  if [[ ! "$name" =~ ^[A-Za-z0-9._-]+$ ]] || [[ ! "$path" =~ ^[A-Za-z0-9._/-]+$ ]]; then
    echo "register-project: invalid characters in name/path" >&2
    return 1
  fi
  printf '\nPROJECTS[%s]="%s"\n' "$name" "$path" >> "$HOME/.zshrc"
}
