Status: PARTIAL
Last verified: 2026-04-17
Verified by: Codex
Doc type: reference

# Spell Slot Pipeline V1

This note defines the first managed spell-slot pipeline for WM.

The goal is not freeform client spell invention.
The goal is to manage spell-side behavior through reserved spell slots, server-side helper tables, publish logs, rollback snapshots, and explicit learn/grant discipline.

---

## What this pipeline is for

This pipeline is for:

- reserving a WM-owned spell slot
- validating one managed spell draft before any live mutation
- discovering the live spell-helper schema instead of assuming one exact core shape
- publishing controlled `spell_linked_spell` and `spell_proc` rows for that slot
- snapshotting the previous state before replacement
- rolling the slot back cleanly to either:
  - `staged` when no previous rows existed
  - `active` when previous rows are restored

This keeps spell-side helper/proc work inside the same slot-governed lifecycle already used for quests and items.

---

## Current repo proof

`WORKING`: repo-tested spell publish/rollback lane.

- `python -m wm.spells.publish` validates managed spell drafts, checks required tables, discovers supported live column names for `spell_linked_spell` and `spell_proc`, captures rollback previews, and builds deterministic SQL plans.
- `python -m wm.spells.rollback` reads the latest spell rollback snapshot, restores or clears spell-side rows, updates `wm_reserved_slot`, and returns structured issues for missing snapshots, malformed snapshot payloads, missing live tables, unsupported live columns, or MySQL failures.
- `python -m wm.content.workbench` can already allocate passive, item-trigger, and visible spell-slot drafts and can optionally learn/unlearn a published spell on a player through the existing runtime lane.

`PARTIAL`: BridgeLab live proof is not yet complete for a spell-side publish -> learn/grant -> rollback loop on `127.0.0.1:33307`.

Do not mark the spell pipeline fully live-proven until one managed spell slot is:

1. published on BridgeLab
2. granted or learned on the validation player
3. inspected in the live DB/runtime
4. rolled back successfully

---

## Slot kinds

Spell Slot Pipeline V1 uses four slot kinds:

### 1. `visible_spell_slot`

For player-facing spells that must bind to a curated visible slot.

Use it for:

- pre-seeded visible spell entries
- controlled tuning around a known client-known visible spell
- visible shell-bank or learnable spell lanes where client truth already exists

### 2. `passive_slot`

For passives and aura-like behavior.

Use it for:

- passives granted by items or quests
- helper/passive grants tracked in `wm_spell_grant`
- server-side proc and link rules behind a managed slot

### 3. `helper_slot`

For backend-only glue behavior.

Use it for:

- linked spell chains
- proc carrier helpers
- internal aura glue
- hidden server-side reactions that still stay under WM ownership

### 4. `item_trigger_slot`

For item-driven behavior tracked as a WM artifact.

Use it for:

- on-use item spells
- proc-on-hit item behavior
- item-trigger wrapper logic bound to a managed item slot

---

## Live tables and contracts

Required tables:

- `wm_publish_log`
- `wm_rollback_snapshot`

Optional/live-discovered tables:

- `wm_reserved_slot`
- `spell_linked_spell`
- `spell_proc`

Design rule:

- the pipeline discovers live helper-table column names at preflight time
- it does not assume one exact emulator schema
- if the live realm does not expose the required table or supported columns for the requested behavior, publish/rollback must stop with explicit issues instead of partially mutating

---

## Draft shape

Example draft:

```json
{
  "spell_entry": 940000,
  "slot_kind": "item_trigger_slot",
  "name": "Marshal Token Trigger",
  "helper_spell_id": 133,
  "trigger_item_entry": 910000,
  "aura_description": "Prototype managed trigger used by a WM item reward.",
  "proc_rules": [
    {
      "spell_id": 940000,
      "proc_flags": 0,
      "chance": 25.0,
      "cooldown": 0,
      "charges": 0
    }
  ],
  "linked_spells": [
    {
      "trigger_spell_id": 940000,
      "effect_spell_id": 133,
      "link_type": 0,
      "comment": "Prototype trigger to effect link"
    }
  ],
  "tags": ["wm_generated", "spell_slot", "item_trigger"]
}
```

Bundled repo example:

- `control/examples/spells/defias_pursuit_instinct.json`

---

## Publish behavior

On publish, the spell pipeline:

1. validates the managed spell draft
2. checks live table presence and supported column names
3. inspects the reserved slot when `wm_reserved_slot` exists
4. captures a rollback snapshot preview from the live spell-side tables
5. builds deterministic delete/insert SQL for the requested helper/proc rows
6. on apply:
   - logs publish start
   - stores a rollback snapshot
   - replaces live rows for the managed spell slot
   - logs publish success
   - marks the reserved slot `active` when slot tracking is present

Dry-run example:

```bash
python -m wm.spells.publish \
  --draft-json control/examples/spells/defias_pursuit_instinct.json \
  --mode dry-run \
  --summary
```

Demo draft example:

```bash
python -m wm.spells.publish --demo --mode dry-run --summary
```

---

## Rollback behavior

Rollback uses the latest `wm_rollback_snapshot` row for `artifact_type = 'spell'`.

Apply behavior:

- if the snapshot had no previous `spell_linked_spell` or `spell_proc` rows, rollback clears current managed rows and marks the reserved slot `staged`
- if the snapshot had previous helper/proc rows, rollback restores them and keeps the reserved slot `active`
- malformed snapshots, missing snapshot ids, unsupported live restore tables/columns, and MySQL failures return structured issues
- rollback must not silently treat malformed sections as “empty slot” and delete live rows

Dry-run:

```bash
python -m wm.spells.rollback \
  --spell-entry 940000 \
  --mode dry-run \
  --runtime-sync off \
  --summary
```

Apply:

```bash
python -m wm.spells.rollback \
  --spell-entry 940000 \
  --mode apply \
  --runtime-sync soap \
  --soap-command ".reload spell_linked_spell" \
  --summary
```

Runtime note:

- there is no universal spell-helper reload contract across cores/modules
- if the realm does not have a known live reload path for the changed tables, restart worldserver before judging rollback state

---

## Content workbench integration

The content workbench is already the fast operator lane around this pipeline.

Draft allocation:

```bash
python -m wm.content.workbench new-passive --name "Defias Pursuit Instinct"
python -m wm.content.workbench new-trigger-spell --name "Marshal Token Trigger" --trigger-item-entry 910000
python -m wm.content.workbench new-visible-spell --name "Lantern Burst" --base-visible-spell-id 133
```

Publish and optionally learn:

```bash
python -m wm.content.workbench publish-spell \
  --draft-json control/examples/spells/defias_pursuit_instinct.json \
  --mode dry-run
```

The workbench may learn/unlearn a published spell on a player, but that runtime learn/grant proof is still separate from proving the underlying publish/rollback lane.

---

## What this slice does not claim yet

Not yet:

- full BridgeLab publish -> learn -> rollback proof for one managed spell slot
- automatic client patch management for truly new visible spells
- arbitrary live mutation of client-defined spell rows
- universal live reload support for every helper table on every core
- shell-bank proof being complete just because helper/proc tables publish cleanly

Those are later layers after the current spell-side helper/proc loop is proven live.
