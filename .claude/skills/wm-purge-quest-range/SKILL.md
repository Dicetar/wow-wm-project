---
name: wm-purge-quest-range
description: Bulk-remove managed quests across an ID range (cleanup of a reserved/demo quest band). Use this WHENEVER you need to wipe a block of managed quests — resetting a demo, clearing an arc's reserved range, or removing a batch of test quests. Triggers: "purge quests 910500-910549", "clear the demo quest range", "remove all managed quests in this band", "reset the reserved quest slots". Always dry-run first; this is destructive.
---

# Purge a managed quest ID range

Removes managed quest rows across `[start-id, end-id]` (quest_template + related
rows) and frees their reserved slots. Intended for **managed/reserved ranges**
(e.g. a module's `id_ranges.quest`), not stock content.

This is **destructive** — always `--mode dry-run` first to review the set, then
`--mode apply`.

```bash
# review what would be purged
WM_WORLD_DB_PORT=33307 \
  python -m wm.quests.purge_range --start-id 910500 --end-id 910549 --mode dry-run --summary
# apply
WM_WORLD_DB_PORT=33307 \
  python -m wm.quests.purge_range --start-id 910500 --end-id 910549 --mode apply --summary
```
- `--include-reactive` also clears reactive-bounty quests in the range.
- `--output-json <path>` writes the full result.
- After applying, **reload the worldserver** (`.reload all quest`) so it forgets
  the purged quests — see wm-reload-worldserver.

## Gotchas
- Picking a range that overlaps stock quest IDs → don't; keep to reserved managed
  bands. Dry-run shows exactly which IDs are in scope.
- Players still see a purged quest in their log → that's client/in-memory state;
  the template is gone, reload + relog clears it.
- To undo a single managed quest instead of a whole band, use **wm-rollback**
  (snapshot restore) rather than purge.
