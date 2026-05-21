---
name: wm-create-quest
description: Author and publish a new managed quest into the WM world DB. Use this WHENEVER you need a brand-new quest to exist on the server — a custom kill/bounty quest, a demo or arc quest, or any quest the WM grants. Do NOT hand-write quest_template SQL or clone stock quests; this pipeline validates, stages a reserved ID slot, snapshots for rollback, publishes, and reloads the worldserver. Triggers: "create a quest", "make a managed quest", "publish a quest", "I need a new quest for the arc/bounty".
---

# Create a managed quest

Publishes a genuinely new quest through `wm.quests.publish` — the project's
quest pipeline. It validates the draft, stages the reserved ID slot, writes a
rollback snapshot + publish log, inserts `quest_template` (+addon/offer/request
rows), and you then reload the worldserver. **Never** hand-roll `quest_template`
SQL or clone a stock quest by copying rows — that produces reskins, skips
rollback tracking, and collides with quest history.

## Scope / capability
The pipeline produces **kill-bounty** quests (kill N of a target creature). For
other objective types (gather, escort, talk-only), this skill does not yet apply
— flag that as a pipeline gap rather than faking it with raw SQL.

## Prerequisites
- A managed quest **ID in a reserved range** (e.g. the story module's
  `id_ranges.quest`). The ID's slot must be **staged** before publish.
- The **target creature must already exist** in `creature_template`.
- For **direct grant with no NPC `!` offer leak**: set `start_npc_entry: null`
  and `grant_mode: "direct_quest_add"`. Set `end_npc_entry` to an existing NPC
  (e.g. 197 / McBride) so the quest can be turned in.
- BridgeLab DB is on port **33307**, SOAP on **7879** (override the defaults).

## Steps

### 1. Write the draft JSON
Put it under `control/examples/quest_drafts/<name>.quest.json`. Required shape:
```json
{
  "quest_id": 910500, "quest_level": 2, "min_level": 1,
  "questgiver_entry": 197, "questgiver_name": "Marshal McBride",
  "title": "An Unfamiliar Weight",
  "quest_description": "<prose shown on accept>",
  "objective_text": "Cull Kobold Vermin in the Northshire valley.",
  "offer_reward_text": "<prose on turn-in>",
  "request_items_text": "<prose while incomplete>",
  "objective": {"target_entry": 6, "target_name": "Kobold Vermin", "kill_count": 4},
  "reward": {"money_copper": 250, "reward_xp_difficulty": 2},
  "start_npc_entry": null,
  "end_npc_entry": 197,
  "grant_mode": "direct_quest_add",
  "tags": ["wm-slice", "<module>", "<beat>"]
}
```
`grant_mode` MUST be `direct_quest_add` or `npc_start` (anything else fails validation).

### 2. Stage the reserved slot
The slot starts `free`; publish requires `staged`:
```python
import dataclasses
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.reserved.db_allocator import ReservedSlotDbAllocator
s = dataclasses.replace(Settings.from_env(), world_db_port=33307)
ReservedSlotDbAllocator(MysqlCliClient(), s).ensure_slot_prepared(entity_type="quest", reserved_id=910500)
```

### 3. Dry-run, then apply
```bash
WM_WORLD_DB_PORT=33307 WM_CHAR_DB_PORT=33307 WM_SOAP_PORT=7879 \
  python -m wm.quests.publish --draft-json control/examples/quest_drafts/<name>.quest.json --mode dry-run --summary
# fix any validation/preflight issues, then:
WM_WORLD_DB_PORT=33307 WM_CHAR_DB_PORT=33307 WM_SOAP_PORT=7879 \
  python -m wm.quests.publish --draft-json control/examples/quest_drafts/<name>.quest.json --mode apply --summary
```
Look for `applied: true`, `validation.ok: true`, `preflight.ok: true`. (A "quest
ID already exists" warning just means a prior row will be replaced — fine.)

### 4. Reload the worldserver
A running worldserver caches `quest_template` at startup; the new quest is
invisible until reloaded:
```python
import dataclasses
from wm.config import Settings
from wm.runtime_sync import SoapRuntimeClient
s = dataclasses.replace(Settings.from_env(), soap_port=7879)
SoapRuntimeClient(settings=s).execute_command(".reload all quest")
```

### 5. Verify
```sql
SELECT ID, LogTitle, RequiredNpcOrGo1, RequiredNpcOrGoCount1
FROM quest_template WHERE ID = 910500;
```

## Then what
To actually give the quest to a player, use the **wm-grant-quest** skill (the
quest existing in the DB does not put it in anyone's log).

## Gotchas
- Forgot to reload → grant fails with "quest does not exist".
- Slot not staged → preflight error `reserved_slot ... status free; expected staged`.
- Added `creature_queststarter` (via `start_npc_entry`) → the quest leaks as a
  `!` offer to every player who talks to that NPC. Keep it `null` for managed grants.
