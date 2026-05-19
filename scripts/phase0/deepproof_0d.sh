#!/usr/bin/env bash
# Deeper 0D proof: real SUCCESSFUL mutations through the post-0D
# domain-split dispatch, verified against actual game state.
# Requires Jecia (5406) online. Mutations are tiny/lab-harmless.
set -euo pipefail
M(){ "/d/WOW/WM_BridgeLab/deps/mysql/bin/mysql.exe" --host=127.0.0.1 --port=33307 --user=acore --password=acore --default-character-set=utf8mb4 "$@"; }
TAG="deep0d-$(date +%s)"

online=$(M acore_characters -N -e "SELECT online FROM characters WHERE guid=5406;")
[ "$online" = "1" ] || { echo "ABORT: Jecia (5406) is NOT online (online=$online). Log in first."; exit 1; }

money0=$(M acore_characters -N -e "SELECT money FROM characters WHERE guid=5406;")
cloth0=$(M acore_characters -N -e "SELECT COALESCE(SUM(ii.count),0) FROM character_inventory ci JOIN item_instance ii ON ii.guid=ci.item WHERE ci.guid=5406 AND ii.itemEntry=2589;")
echo "BEFORE: money=$money0  linen_cloth(2589)=$cloth0"

ins(){ M acore_world -e "INSERT INTO wm_bridge_action_request (IdempotencyKey,PlayerGUID,ActionKind,PayloadJSON,Status,CreatedBy,RiskLevel) VALUES ('${TAG}-$1',5406,'$1','$2','pending','wm-test','low');"; }
ins player_add_money  '{"amount":1234}'
ins player_add_item   '{"item_id":2589,"count":3}'

echo "inserted; waiting for poll..."
sleep 14

echo "=== result JSON (post-0D player + inventory TUs) ==="
M acore_world -N -e "SELECT ActionKind,Status,ResultJSON,COALESCE(ErrorText,'<null>') FROM wm_bridge_action_request WHERE IdempotencyKey LIKE '${TAG}-%' ORDER BY ActionKind;"

money1=$(M acore_characters -N -e "SELECT money FROM characters WHERE guid=5406;")
cloth1=$(M acore_characters -N -e "SELECT COALESCE(SUM(ii.count),0) FROM character_inventory ci JOIN item_instance ii ON ii.guid=ci.item WHERE ci.guid=5406 AND ii.itemEntry=2589;")
echo "AFTER:  money=$money1  linen_cloth(2589)=$cloth1"
echo "DELTA:  money=$((money1-money0)) (expect 1234)  cloth=$((cloth1-cloth0)) (expect 3)"
[ $((money1-money0)) -eq 1234 ] && [ $((cloth1-cloth0)) -eq 3 ] \
  && echo "DEEP 0D PROOF: PASS ✓ (real mutations executed through split TUs)" \
  || echo "DEEP 0D PROOF: FAIL ✗"
