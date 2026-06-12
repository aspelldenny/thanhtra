#!/usr/bin/env bash
# render-clip: CI render job — data đi qua env var, heredoc quoted delimiter (đã sửa)

BRANCH="$1"
CONFIG="content/clips.json"

clip=$(jq -c --arg b "$BRANCH" '.clips[] | select(.branch == $b)' "$CONFIG")

CLIP_JSON="$clip" python3 <<'EOF'
import json, os
clip = json.loads(os.environ["CLIP_JSON"])
print("rendering clip")
EOF
