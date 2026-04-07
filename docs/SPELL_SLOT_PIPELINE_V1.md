# Spell Slot Pipeline V1

This note fixes the contract for the next WM live-content slice after the managed item-slot loop.

The goal is **not** fully freeform spell invention.
The goal is to manage spell / passive / helper behavior through **reserved spell slots** and controlled server-side tables.

---

## Why this slice exists

The item pipeline can already assign spell slots on an item row, but the repo still lacks a dedicated WM-side contract for:

- visible player-facing spell slots
- passive aura slots
- helper / backend trigger slots
- item-triggered spell behavior

Without a spell-slot contract, the item slice can only point at hard-coded spell IDs and cannot safely evolve into a broader WM ability pipeline.

---

## Slot kinds

Spell Slot Pipeline V1 uses four slot kinds:

### 1. `visible_spell_slot`
For player-facing spells that should be treated as curated visible slots.

Expected use:
- pre-seeded visible spell entries
- controlled tuning around a known base visible spell
- launcher/client patch discipline stays outside the WM repo

### 2. `passive_slot`
For passives and aura-like behavior.

Expected use:
- passives granted by items or quests
- passives represented by known visible or helper spell IDs
- server-side proc and link rules

### 3. `helper_slot`
For backend-only glue behavior.

Expected use:
- linked spell chains
- internal aura glue
- proc carrier helpers
- invisible server-side reactions

### 4. `item_trigger_slot`
For item-driven behavior that should be tracked as a WM artifact.

Expected use:
- on-use item spells
- proc-on-hit item behavior
- item-trigger wrapper logic tied to a managed item slot

---

## Current repo groundwork added now

The repo now has the first managed spell draft layer:

- `src/wm/spells/models.py`
- `src/wm/spells/validator.py`

This is not the full publish pipeline yet.
It is the contract layer that lets the next implementation step stay disciplined.

---

## Draft shape

Example:

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

---

## Validation goals already fixed

The new validator enforces:

- positive `spell_entry`
- allowed `slot_kind`
- non-empty operator-facing name
- `visible_spell_slot` requires `base_visible_spell_id`
- `item_trigger_slot` requires `trigger_item_entry`
- proc rules and linked spells must reference positive spell IDs

That is enough to keep future publish work from being built on garbage inputs.

---

## Planned publish scope for the next spell slice

The next implementation step should publish controlled WM spell behavior through server-side tables only.

Target tables should be discovered live during preflight and treated as optional/required depending on the path:

- `spell_linked_spell`
- `spell_proc`
- any other installed server-side spell helper tables present on the real realm

The spell slice should remain:

- lookup-first
- validation-first
- runtime-aware
- slot-governed

It should **not** assume free live mutation of client-defined visible spells.

---

## Recommended implementation order

### Phase A — spell contract and validation
Done now.

### Phase B — server-side helper/proc publish
Next step.

Build:
- `wm.spells.publish`
- preflight for supported live tables
- rollback snapshots / publish logs
- managed reserved slot checks for `EntityType = 'spell'`

### Phase C — item-trigger integration
After helper/proc publish works.

Build one straight-through proof:
- managed item slot
- managed spell/item-trigger slot
- quest rewards the managed item
- item uses or procs the managed spell behavior

### Phase D — passive/quest-granted ability integration
After item-trigger flow is proven.

---

## Operational rule

Spell Slot Pipeline V1 should follow the same repo rules already used elsewhere:

- concise output only
- summary-first terminal output
- JSON artifacts for details
- dry-run before apply
- rollback path defined before live mutation

---

## What is intentionally not claimed yet

Not yet:

- a finished live spell publisher
- client patch management
- dynamic creation of truly new client-visible spell definitions
- guaranteed universal support for every emulator-side spell helper table

This note exists to lock down the next safe target, not to pretend the spell slice is already finished.
