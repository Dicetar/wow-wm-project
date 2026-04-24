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
- `python -m wm.spells.live_publish` wraps publish plus optional runtime sync for the same draft, mirroring the managed item live wrapper instead of forcing operators to stitch publish and reload steps by hand.
- `python -m wm.spells.rollback` reads the latest spell rollback snapshot, restores or clears spell-side rows, updates `wm_reserved_slot`, revokes active `wm_spell_grant` rows for that spell when the table exists, and returns structured issues for missing snapshots, malformed snapshot payloads, missing live tables, unsupported live columns, or MySQL failures.
- `python -m wm.content.workbench` can already allocate passive, item-trigger, and visible spell-slot drafts and can optionally learn/unlearn a published spell on a player through the existing runtime lane.
- managed spell-slot learns and revokes are now tracked in `wm_spell_grant` when the spell id is WM-owned, `publish-spell --learn-to-player-*` no longer attempts the runtime learn when publish validation, preflight, or apply failed, visible spell slots resolve runtime learn through `base_visible_spell_id` instead of trying to teach the reserved artifact id directly, and apply-mode learn/unlearn now verifies the expected `character_spell` row before reporting success.
- `wm.reserved.db_allocator` now defends the managed spell-slot band against stale BridgeLab rows in the old shell range: spell allocation skips exact claimed ids and any `wm_reserved_slot` row outside the managed range `947000-947999`.

`PARTIAL`: BridgeLab live proof is not yet complete for a spell-side publish -> learn/grant -> rollback loop on `127.0.0.1:33307`.

BridgeLab attempt on 2026-04-17:

- `Publish-BridgeLabManagedSpell.ps1` published bundled draft `947000` successfully and stored rollback snapshot `57`
- `Grant-BridgeLabManagedSpell.ps1` then failed to learn the spell for player `5406`
- local BridgeLab source confirms `.player learn <player> <spell> [all]` is the valid GM-console command shape, so the blocker was not just command syntax
- structural reason: managed spell slot `947000` is only a helper/proc-governed WM slot; it is not a server-known spell row or shell-backed learnable spell identity, so learn/grant cannot succeed on this lane yet
- secondary environment gap: BridgeLab world DB also had no `wm_reserved_slot` row for spell `947000`, so slot tracking was warning-only during publish

BridgeLab follow-up on 2026-04-17 after the repo/runtime-target hardening:

- BridgeLab was still carrying stale free/staged spell reserved rows in the old shell band (`940000+`), including staged rows for `940000` / `940001`; managed spell allocation is now guarded in code and the lab was reseeded for `947000-947999`
- a fresh visible-slot draft allocated `947001` correctly after the allocator fix
- publish of `947001` succeeded and a runtime learn was attempted through `base_visible_spell_id=133`
- native `player_learn_spell` remained policy-disabled, so the workbench fell back to SOAP
- later hardening added a `.saveall` flush plus short retry window to spell learn/unlearn verification, and that change was enough to prove the separate shell-backed server path; it did not remove the managed-slot structural blocker
- rollback for `947001` succeeded from snapshots `58` and `59`, returned the reserved slot to `staged`, and manual cleanup unlearn of stock proof spell `133` verified `character_spell` absence as expected

Current truth:

- `WORKING`: repo-side publish / rollback governance, runtime-sync wrapper, `wm_spell_grant` tracking, and rollback cleanup
- `WORKING`: visible-slot runtime target resolution and post-apply `character_spell` verification at repo-test level, including `.saveall` flush plus retry-backed DB checks
- `PARTIAL`: live managed-slot grant/learn proof
- the separate named-shell server lane is now a real learnable identity on BridgeLab, but managed slots still need either shell/client truth or an explicit materialization step before they can claim the same status
- do not trust raw SOAP success or `already know that spell` for this lane without a matching `character_spell` or equivalent live player proof

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
  "spell_entry": 947000,
  "slot_kind": "item_trigger_slot",
  "name": "Marshal Token Trigger",
  "helper_spell_id": 133,
  "trigger_item_entry": 910000,
  "aura_description": "Prototype managed trigger used by a WM item reward.",
  "proc_rules": [
    {
      "spell_id": 947000,
      "proc_flags": 0,
      "chance": 25.0,
      "cooldown": 0,
      "charges": 0
    }
  ],
  "linked_spells": [
    {
      "trigger_spell_id": 947000,
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

Live wrapper example:

```bash
python -m wm.spells.live_publish \
  --draft-json control/examples/spells/defias_pursuit_instinct.json \
  --mode apply \
  --runtime-sync off \
  --summary
```

If the realm has a known spell-side reload path, pass it explicitly:

```bash
python -m wm.spells.live_publish \
  --draft-json control/examples/spells/defias_pursuit_instinct.json \
  --mode apply \
  --runtime-sync soap \
  --soap-command ".reload spell_linked_spell" \
  --summary
```

---

## Rollback behavior

Rollback uses the latest `wm_rollback_snapshot` row for `artifact_type = 'spell'`.

Apply behavior:

- if the snapshot had no previous `spell_linked_spell` or `spell_proc` rows, rollback clears current managed rows and marks the reserved slot `staged`
- if the snapshot had previous helper/proc rows, rollback restores them and keeps the reserved slot `active`
- if `wm_spell_grant` exists, rollback also revokes any still-active grant rows for that spell entry so grant state does not remain falsely active after artifact rollback
- malformed snapshots, missing snapshot ids, unsupported live restore tables/columns, and MySQL failures return structured issues
- rollback must not silently treat malformed sections as “empty slot” and delete live rows

Dry-run:

```bash
python -m wm.spells.rollback \
  --spell-entry 947000 \
  --mode dry-run \
  --runtime-sync off \
  --summary
```

Apply:

```bash
python -m wm.spells.rollback \
  --spell-entry 947000 \
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

BridgeLab proof helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bridge_lab\Publish-BridgeLabManagedSpell.ps1 `
  -DraftPath control\examples\spells\defias_pursuit_instinct.json `
  -Mode dry-run `
  -RuntimeSync off
```

BridgeLab grant helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bridge_lab\Grant-BridgeLabManagedSpell.ps1 `
  -DraftPath .wm-bootstrap\state\content-drafts\bridge-lab-visible-proof-5406.json `
  -PlayerGuid 5406 `
  -Mode apply `
  -WaitForPlayerOnline
```

Helper rule:

- when `-DraftPath` points at a `visible_spell_slot`, the helper now learns `base_visible_spell_id`
- when `-DraftPath` points at `passive_slot`, `helper_slot`, or `item_trigger_slot`, the helper now stops immediately with an explicit error instead of trying to learn the reserved artifact id

BridgeLab rollback helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bridge_lab\Rollback-BridgeLabManagedSpell.ps1 `
  -SpellEntry 947000 `
  -Mode dry-run `
  -RuntimeSync off
```

Governance rule:

- direct learn/unlearn should record `wm_spell_grant` only for WM-owned spell ids
- rollback should revoke active `wm_spell_grant` rows for the rolled-back WM spell id when the table exists
- do not treat arbitrary stock spell learns as managed WM grants

Hard rule:

- managed spell drafts must not reuse named shell-bank spell ids such as `940000`, `940001`, `944000`, or `945000`
- use the managed spell-slot range `947000-947999` instead

---

## What this slice does not claim yet

Not yet:

- full BridgeLab publish -> learn -> rollback proof for one managed spell slot
- live player unlearn / post-rollback runtime cleanup proof for managed spell grants
- a shell-backed visible spell learn path that is both server-known and client-known in BridgeLab
- automatic client patch management for truly new visible spells
- arbitrary live mutation of client-defined spell rows
- universal live reload support for every helper table on every core
- shell-bank proof being complete just because helper/proc tables publish cleanly

Those are later layers after the current spell-side helper/proc loop is proven live.
