# Demo managed quest drafts

Genuinely-new managed quests for the WM vertical-slice demo module
(`../story_modules/demo_one.story_module.json`). These are **not** clones of
stock quests — each has its own title, narrative, and a real kill objective
against an existing Northshire creature. They live in the module's reserved
ID range (910500–910549).

| Draft | Quest ID | Beat | Objective |
|---|---|---|---|
| `b00_unfamiliar_weight.quest.json` | 910500 | b00 PINNED onboarding | 4× Kobold Vermin (6) |
| `b01_echo_ridge.quest.json` | 910502 | b01 OPEN fixture | 6× Young Wolf (299) |
| `b03_watchers_lash.quest.json` | 910501 | b03 PINNED finale | 8× Stonetusk Boar (113) |

`grant_mode` is `direct_quest_add` and `start_npc_entry` is `null`, so the
quests are granted directly by the slice (native-bus `quest_add`) with **no**
`creature_queststarter` row — avoiding the NPC-offer leak (Blocker #3). They
turn in at Marshal McBride (`end_npc_entry: 197`).

## Publish (per draft)

The reserved slot must be staged first, then publish, then reload the
worldserver. Against BridgeLab (MySQL 33307, SOAP 7879):

```bash
# 1. stage the reserved slot (wm.reserved.db_allocator.ensure_slot_prepared)
# 2. publish:
WM_WORLD_DB_PORT=33307 WM_CHAR_DB_PORT=33307 WM_SOAP_PORT=7879 \
  python -m wm.quests.publish --draft-json <draft>.quest.json --mode apply --summary
# 3. reload: .reload all quest  (via SoapRuntimeClient)
```

Publishing writes `quest_template` (+ addon), a `wm_rollback_snapshot`, and a
`wm_publish_log` entry — so each quest is rollback-tracked, unlike a raw clone.
