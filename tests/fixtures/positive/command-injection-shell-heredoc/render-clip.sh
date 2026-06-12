#!/usr/bin/env bash
# render-clip: CI render job — workflow gọi với branch name của PR contributor

BRANCH="$1"   # github.head_ref — L1, contributor đặt tên branch tùy ý
CONFIG="content/clips.json"

clip=$(jq -c --arg b "$BRANCH" '.clips[] | select(.branch == $b)' "$CONFIG")

python3 <<EOF
import json
clip = json.loads('$clip')
print("rendering clip")
EOF
