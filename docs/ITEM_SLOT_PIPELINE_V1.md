# Item Slot Pipeline V1

This note defines the first **managed item-slot** pipeline for the WM repo.

The quest platform already works live.
The missing companion piece is a way to create or edit a **managed custom item slot** and then use that item as a quest reward.

This slice does **not** attempt fully freeform item generation.
It uses the same discipline already established for quests:

- managed slots
- validation first
- publish logs
- rollback snapshots
- runtime-aware operator guidance

---

## What this pipeline is for

This pipeline is for:

- cloning a known-good base item row from `item_template`
- rewriting it into a WM-managed item slot
- storing rollback history before replacement
- optionally sending server-specific runtime reload commands
- reusing the resulting item entry in quest rewards

This matches the slot-based architecture established earlier for WM item work.

---

## Why clone from a base item

AzerothCore-style `item_template` rows are wide and schema-sensitive.

Instead of trying to synthesize every field from scratch, Item Slot Pipeline V1 does this:

1. read a real base item row from `item_template`
2. clone the full row
3. replace the `entry` with a WM-managed item slot
4. apply controlled overrides:
   - name
   - description
   - display
   - quality
   - item / required level
   - binding / price / stack settings
   - stats
   - spell slots
5. publish the final row back into `item_template`

That keeps the first item slice practical and much safer than raw freeform item synthesis.

---

## New commands

### Publish planning / apply

```bash
python -m wm.items.publish --demo --mode dry-run --summary
python -m wm.items.publish --demo --mode apply --summary --output-json .\artifacts\item_910000_publish.json
```

### Live publish wrapper

```bash
python -m wm.items.live_publish --demo --mode apply --runtime-sync off --summary
```

You can also send your own SOAP command if your server has a known item reload command or a module-specific reload path:

```bash
python -m wm.items.live_publish ^
  --draft-json .\artifacts\managed_item.json ^
  --mode apply ^
  --runtime-sync soap ^
  --soap-command ".reload item_template" ^
  --summary
```

The pipeline does **not** assume a universal item reload command.
If no runtime command is supplied, it publishes to DB and recommends restart/testing discipline instead.

---

## Managed draft shape

Example draft:

```json
{
  "item_entry": 910000,
  "base_item_entry": 6948,
  "name": "Marshal's Field Token",
  "description": "A WM-managed prototype reward item.",
  "quality": 2,
  "item_level": 10,
  "required_level": 1,
  "stackable": 1,
  "max_count": 1,
  "clear_spells": true,
  "stats": [
    {"stat_type": 7, "stat_value": 4},
    {"stat_type": 4, "stat_value": 3}
  ],
  "spells": [],
  "tags": ["wm_generated", "managed_item_slot", "quest_reward"]
}
```

Important fields:

- `item_entry`: the WM-managed slot to publish into
- `base_item_entry`: the known-good item row to clone
- `clear_stats`: wipe inherited stat slots before applying provided `stats`
- `clear_spells`: wipe inherited spell slots before applying provided `spells`

---

## Reserved slots

The generic slot seeder already supports `item`:

```bash
python -m wm.reserved.seed --entity-type item --start-id 910000 --end-id 910099 --mode apply --summary
```

The item publisher checks `wm_reserved_slot` for `EntityType = 'item'` and will warn when the managed slot is not wired yet.

---

## Publish behavior

On apply, the item publisher:

1. validates the managed item draft
2. checks live schema / base row / slot conditions
3. captures rollback snapshot preview
4. logs publish start in `wm_publish_log`
5. stores the old row snapshot in `wm_rollback_snapshot`
6. replaces the `item_template` row for the managed slot
7. logs success
8. marks the slot `active` when `wm_reserved_slot` is present

This mirrors the quest pipeline discipline.

---

## How to reward the item from a quest

The quest pipeline already supports item rewards.

That means the shortest integration path is:

1. publish the managed item slot
2. use the resulting item entry in quest generation or live quest edit

For an existing quest:

```bash
python -m wm.quests.edit_live ^
  --quest-id 910005 ^
  --reward-item-entry 910000 ^
  --reward-item-count 1 ^
  --mode apply ^
  --runtime-sync auto ^
  --summary
```

So the item slice becomes useful immediately even before there is a dedicated quest↔item orchestration command.

---

## What this slice does not do yet

Not yet:

- automatic client patch management
- item_template_locale support
- inventory-aware safety checks for players already owning a slot
- copy-on-publish retirement discipline for item slots
- spell-slot registry governance
- a dedicated managed spell / passive / ability pipeline

Those are the next layers after the first managed item slot loop is proven.

---

## Immediate next step after this slice

After validating the item slot loop on the real server, the next best continuation is:

1. add rollback command support for managed items
2. add one quest-demo flow that:
   - publishes a managed item
   - rewards it from a live quest
   - edits that reward cleanly
3. then build **Spell Slot Pipeline V1** for:
   - visible spell slots
   - passive/helper slots
   - item-trigger and quest-reward integration

That gives the WM a coherent progression:

- quests
- item slots
- spell / passive / ability slots
