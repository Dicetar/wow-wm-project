#!/usr/bin/env bash
# 0D live-proof capture. Usage: capture.sh <tag>  -> writes phase0d/<tag>.txt
set -euo pipefail
TAG="$1"
MYSQL="/d/WOW/WM_BridgeLab/deps/mysql/bin/mysql.exe"
OUT="/d/WOW/wm-project/artifacts/phase0d/${TAG}.txt"
M() { "$MYSQL" --host=127.0.0.1 --port=33307 --user=acore --password=acore --default-character-set=utf8mb4 acore_world "$@"; }

ins() { # kind  payload
  M -e "INSERT INTO wm_bridge_action_request (IdempotencyKey,PlayerGUID,ActionKind,PayloadJSON,Status,CreatedBy,RiskLevel) VALUES ('${TAG}-$1-$(date +%s%N)',5406,'$1','$2','pending','wm-test','low');"
}

ins debug_ping '{}'
ins debug_echo '{"msg":"hello world snowman ☃ accent eee q backslash"}'
ins debug_fail '{}'
ins player_add_money '{"amount":5}'
ins player_add_item '{"item_id":6948,"count":1}'
ins quest_add '{"quest_id":2}'
ins creature_despawn '{}'
ins context_snapshot_request '{"context_kind":"nearby","radius":20}'
ins world_announce_to_player '{"message":"hi"}'

sleep 18

M -N -e "SELECT ActionKind, Status, ResultJSON, COALESCE(ErrorText,'<null>') FROM wm_bridge_action_request WHERE IdempotencyKey LIKE '${TAG}-%' ORDER BY ActionKind, RequestID;" > "$OUT"
echo "wrote $OUT"
cat "$OUT"
