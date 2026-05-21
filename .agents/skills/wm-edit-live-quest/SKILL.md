---
name: wm-edit-live-quest
description: Edit a published quest's title or rewards in place via the quest edit pipeline. Use this WHENEVER a live managed quest needs a text or reward tweak WITHOUT re-publishing a new ID. Triggers: "change the quest title", "adjust the quest reward", "fix the reward money/xp on quest X", "edit the offer text". CAUTION: never mutate rewards on a quest a live player has already accepted/rewarded — publish a fresh slot instead (wm-content-release rule).
---

# Edit a live quest

Wraps `wm.quests.edit_live` to patch an existing `quest_template` row's title /
reward fields, with the same snapshot + reload discipline as publishing. Sits
under **wm-content-release** (ID/rollback contract) and **wm-live-bridge-lab**
(runtime).

## Hard rule (from wm-content-release)
**Never change rewards on a quest ID a live player has already accepted or been
rewarded for** — that corrupts their state. Publish a fresh quest slot instead
(wm-create-quest). Edits are safe for not-yet-handed-out quests or non-reward
text.

## Use it
```bash
WM_WORLD_DB_PORT=33307 WM_SOAP_PORT=7879 \
  python -m wm.quests.edit_live --quest-id 910500 \
    --title "An Unfamiliar Weight" \
    --reward-money-copper 250 --reward-xp 80 \
    --offer-reward-text "The regard has taken your measure." \
    --mode dry-run
# review, then --mode apply --runtime-sync soap
```
Other flags: `--reward-item-entry` / `--reward-item-count` / `--clear-reward-item`.
Always `--mode dry-run` first; `--runtime-sync soap` triggers the worldserver
reload (`.reload all quest`).

## Verify
```sql
SELECT ID, LogTitle, RewardMoney FROM quest_template WHERE ID = 910500;
```

## Gotchas
- Edit not visible in-game → missing `--runtime-sync soap` (no reload).
- Reward edit on an accepted quest → forbidden; fresh slot instead.
- To undo, use **wm-rollback** (snapshot restore).
