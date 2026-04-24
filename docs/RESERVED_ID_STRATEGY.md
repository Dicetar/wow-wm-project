# Reserved ID Strategy

## Why this exists

World Master needs a place to put **allocator-managed slots** and **future mutable content**.

Instead of inventing IDs ad hoc every time, reserve clean numeric ranges up front for allocator-managed WM content.

This supports the project requirement that WM should eventually be able to:
- rewrite quest arcs
- assign private rewards
- create alternate spell wrappers
- create item-gated abilities
- attach private dialogue and branching conversations

## Current reservation plan

### Managed spell slots
- `947000` to `947999`
- Use for: managed spell publish/rollback slots allocated through `wm_reserved_slot`
- Exact shell-bank spell claims do not live here; they are tracked in `data/specs/custom_id_registry.json`

### Quest slots
- `910000` to `910999`
- Use for: private quest arcs, branch quests, follow-up quests, test quests

### Item slots
- `910000` to `910999`
- Use for: private reward items, equipped-gate items, item prototypes
- Numeric overlap with quest slots is allowed because namespace + id is the real uniqueness boundary

### Gossip menu slots
- `912000` to `912499`
- Use for: WM-authored conversation menus and branch nodes

### NPC text slots
- `912500` to `912999`
- Use for: WM-authored dialogue text blocks

## Important design rule

Reserving a range does **not** mean the rows already exist.

There are two stages:
1. reserve the range
2. later pre-seed dummy rows in that range so WM can safely overwrite/update them

## Why this is useful

This now has two layers:

1. coarse allocator policy in `reserved_id_ranges.json`
2. exact claims in `custom_id_registry.json`

## Current implementation in repo

- `data/specs/reserved_id_ranges.json`
- `data/specs/custom_id_registry.json`
- `sql/bootstrap/wm_reserved_id_ranges.sql`

## Local commands

### Pull latest changes

```powershell
cd D:\WOW\wm-project
git pull origin main
```

### Inspect the JSON spec

```powershell
cd D:\WOW\wm-project
Get-Content .\data\specs\reserved_id_ranges.json
```

### Import the reservation table into `acore_world`

```powershell
cd D:\WOW\wm-project
Get-Content .\sql\bootstrap\wm_reserved_id_ranges.sql | & "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore acore_world
```

### Verify reserved ranges in DB

```powershell
& "D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe" -u acore -pacore -D acore_world -e "SELECT * FROM wm_reserved_id_range ORDER BY EntityType;"
```

## Next implementation target

Current status:

- `WORKING`: allocator-managed quest/item/spell ranges now match the active WM pipelines
- `WORKING`: exact claim tracking moved into `docs/CUSTOM_ID_LEDGER.md` and `data/specs/custom_id_registry.json`
- `PARTIAL`: older historical docs may still mention the retired `spell_dbc_or_spell_slots` / `900000-900999` spell range; trust the ledger and current-state docs instead
