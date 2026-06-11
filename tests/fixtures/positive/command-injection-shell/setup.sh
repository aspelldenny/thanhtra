#!/usr/bin/env bash
# register-project: thêm project vào registry trong shell rc

register-project() {
  local path="$1"
  local name
  name=$(basename "$path")
  printf '\nPROJECTS[%s]="%s"\n' "$name" "$path" >> "$HOME/.zshrc"
}
