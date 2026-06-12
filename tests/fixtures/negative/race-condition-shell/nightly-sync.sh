#!/usr/bin/env bash
# nightly-sync: flock chặn chạy chồng, mktemp + trap cleanup, ghi atomic (đã sửa)

exec 200>/var/lock/nightly-sync.lock
flock -n 200 || exit 0

tmp=$(mktemp) || exit 1
trap 'rm -f "$tmp"' EXIT
jq '.count += 1' state.json > "$tmp" && mv "$tmp" state.json
