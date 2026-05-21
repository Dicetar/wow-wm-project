---
name: wm-rollback
description: Roll back a published managed quest, item, or spell using the rollback snapshot written at publish time. Use this WHENEVER a managed publish was wrong, broke something, or needs to be undone cleanly. Triggers: "roll back that quest/item/spell", "undo the publish", "revert quest 910500", "the managed item is broken, remove it", "restore the pre-publish state". Always dry-run first.
---

# Roll back a managed publish

Every `wm-create-*` publish writes a `wm_rollback_snapshot` (pre-change state) +
a `wm_publish_log` entry. These rollback tools restore from the **latest
snapshot** for the entity — so rollback only works for artifacts published
through the pipeline (not hand-rolled SQL).

Always run `--mode dry-run` first to see what will change, then `--mode apply`.
BridgeLab DB is **33307**, SOAP **7879** (override via env / wrapper).

## Quest
```bash
WM_WORLD_DB_PORT=33307 WM_SOAP_PORT=7879 \
  python -m wm.quests.rollback --quest-id 910500 --mode dry-run --summary
# then --mode apply --runtime-sync soap   (so the worldserver reloads)
```
(`--allow-reactive` to include reactive-bounty quests.)

## Item
```bash
WM_WORLD_DB_PORT=33307 WM_SOAP_PORT=7879 \
  python -m wm.items.rollback --item-entry 910500 --mode apply --runtime-sync soap --summary
```

## Spell
Prefer the BridgeLab wrapper (sets ports):
```powershell
powershell -File scripts/bridge_lab/Rollback-BridgeLabManagedSpell.ps1 `
  -SpellEntry 947000 -Mode apply -RuntimeSync soap
```
Underlying module: `python -m wm.spells.rollback --spell-entry <id> --mode apply`.
**Remember:** a rolled-back `Spell.dbc` shell change needs a worldserver
**restart** (DBC isn't hot-reloadable) — see wm-reload-worldserver.

## Verify
- `--summary` reports what was reverted.
- The reserved slot should return toward `free`/`staged`; `wm_publish_log` gets a
  rollback entry.

## Gotchas
- "No rollback snapshot exists for X" → it wasn't published through the pipeline
  (e.g. a raw-SQL clone). There's nothing to roll back to; clean it manually.
- Forgot `--runtime-sync soap` → DB reverted but the live worldserver still shows
  the old data until reloaded/restarted.
