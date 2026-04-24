Status: PARTIAL
Last verified: 2026-04-24
Verified by: Codex
Doc type: reference

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

## Current live proof

`WORKING`: BridgeLab item reward proof for player `5406` / quest `910024`.

- Managed item slot `910006` publishes `Night Watcher's Lens`.
- Base item: `2994` (`Deprecated Seer's Monocle`), cloned as a cloth head item.
- Reward shape:
  - +8 Intellect
  - +6 Stamina
  - +12 spell power
  - equip spell `132` with trigger `1`, used as the visible `Detect Invisibility` marker aura for the lens
  - native effect in `mod-wm-spells`: while the lens is equipped and the visible aura is present, player weapon auto-attacks and wand auto-repeat shots have a 10% chance to apply or refresh a visible 10-second target debuff (`770`, Faerie Fire)
  - while the WM-tracked target debuff is active, melee/ranged attack outcome rolls against that target halve the defense/miss/dodge/parry/block values covered by the current hook and double the attack crit chance in that hook
  - WM-owned proc hooks can opt into the "effect chance x2" rule while the visible debuff is active; Bonebound Alpha Echo proc chance now doubles against a WM-marked target
- Quest `910024` (`Bounty: Nightbane Dark Runner - Lens`) rewards item `910006` x1 plus the existing 12 silver.
- Retired test slot `910021` was not a valid visual proof after reward mutation because the player had already accepted/rewarded that quest ID before the item reward was attached; use a fresh quest slot when changing visible quest rewards.
- BridgeLab commands on 2026-04-17:

```bash
python -m wm.items.live_publish \
  --draft-json control/examples/items/night_watchers_lens.json \
  --mode apply \
  --runtime-sync soap \
  --soap-command ".reload item_template" \
  --summary

python -m wm.quests.edit_live \
  --quest-id 910024 \
  --reward-item-entry 910006 \
  --reward-item-count 1 \
  --reward-money-copper 1200 \
  --mode apply \
  --runtime-sync auto \
  --summary
```

`PARTIAL`: client-visible behavior of the item passive still needs in-game confirmation after accepting/turning in the fresh quest, equipping the lens, and seeing the target debuff apply/refresh in combat. If the item aura/effect is stale, publish a fresh item slot or restart worldserver; item reload behavior and client item cache behavior are core/module-specific.

`PARTIAL`: arbitrary stock/core proc chance doubling is not proven. The current implementation doubles attack crit chance in the available attack-outcome hook and WM-owned proc hooks that explicitly opt in; adding true global proc-doubling needs a deeper proc-event hook.

Design rule: hidden server-side item effects are allowed only when the player gets an effect indication, and the hidden effect must be gated by that visible aura/buff/debuff state and duration. For this lens, the visible indications are the `Detect Invisibility` wearer aura and the target debuff. Do not repeat the retired `13890` boot-enchant-on-headgear mistake, and do not ship a silent resource/stat/combat mutation.

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

### Content playcycle wrapper

The fastest supported item-effect iteration lane is now:

```bash
python -m wm.content.playcycle item-effect \
  --scenario-json control/examples/content_playcycles/night_watchers_lens_item_effect.json \
  --mode dry-run \
  --summary
```

Supported modes are `dry-run`, `apply`, `verify`, `promote-quest`, and `rollback`.
The v1 scenario contract is `wm.content_playcycle.item_effect.v1`; it composes the existing managed item publisher, runtime-sync wrapper, native `player_add_item`, fresh reactive bounty slot allocation, and item rollback.
It does not accept freeform SQL, GM command generation fields, shell commands, or LLM mutation fields.

`WORKING`: live BridgeLab proof passed on `127.0.0.1:33307` / player `5406` on 2026-04-24. The proof ran dry-run, apply, verify, visible Lens aura/debuff checks, fresh quest promotion into `910075`, reward-panel visibility proof, rollback from snapshot `110`, and optional native `player_remove_item` cleanup request `142`.

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

## Rollback behavior

`WORKING`: managed item rollback is repo-tested through `python -m wm.items.rollback`.

The rollback command reads the latest `wm_rollback_snapshot` row for `artifact_type = 'item'` and restores the managed slot according to the captured pre-publish state:

- if the snapshot had no previous `item_template` row, rollback deletes the managed item row and marks the reserved slot `staged`
- if the snapshot had a previous `item_template` row, rollback replaces the live row with that snapshot and keeps the reserved slot `active`
- malformed or missing snapshots return structured `snapshot` issues instead of raising raw JSON errors
- MySQL apply failures return structured `mysql` issues and recommend a restart/runtime check instead of silently claiming success

Dry-run:

```bash
python -m wm.items.rollback \
  --item-entry 910006 \
  --mode dry-run \
  --runtime-sync off \
  --summary
```

Apply with an explicit runtime reload command when the core supports it:

```bash
python -m wm.items.rollback \
  --item-entry 910006 \
  --mode apply \
  --runtime-sync soap \
  --soap-command ".reload item_template" \
  --summary
```

`PARTIAL`: live rollback of `910006` has not yet been exercised in BridgeLab after the repo tests. Do not mark item rollback fully live-proven until an operator runs dry-run, apply, reload/restart discipline, and verifies the item row/slot state on `127.0.0.1:33307`.

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

So the item slice becomes useful immediately even before there is a dedicated quest-item orchestration command.

---

## What this slice does not do yet

Not yet:

- automatic client patch management
- item_template_locale support
- inventory-aware safety checks for players already owning a slot
- copy-on-publish retirement discipline for item slots
- spell-slot registry governance
- a dedicated managed spell / passive / ability pipeline
- hidden server-side item mechanics without a visible aura, buff, debuff, combat-log/system message, or tooltip indicator that owns the live duration gate
- unrelated stock spell reuse for tooltip text or passive flavor
- custom item mechanics such as "wand can fire while moving"; that is a native combat/action feature, not a safe item-template-only reward
- reusing a quest ID after changing visible rewards in the same client session; the client/server runtime can keep showing the old reward packet, so iterate with a fresh reserved quest slot

Those are the next layers after the first managed item slot loop is proven.

---

## Immediate next step after this slice

After validating the item slot loop on the real server, the next best continuation is:

1. prove `wm.items.rollback` live in BridgeLab for one managed item slot
2. add one quest-demo flow that:
   - publishes a managed item
   - rewards it from a live quest
   - edits that reward cleanly
3. then prove **Spell Slot Pipeline V1** live in BridgeLab for one managed spell slot publish/learn/rollback loop

That gives the WM a coherent progression:

- quests
- item slots
- spell / passive / ability slots
