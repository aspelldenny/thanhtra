#!/usr/bin/env bash
# nightly-sync: cron mỗi phút trên server chung — không lock, temp path đoán được

jq '.count += 1' state.json > /tmp/sync-state.$$
mv /tmp/sync-state.$$ state.json
