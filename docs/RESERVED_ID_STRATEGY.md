# Reserved ID Strategy

## Why this exists

World Master needs a place to put **dummy slots** and **future mutable content**.

Instead of inventing IDs ad hoc every time, reserve clean numeric ranges up front for WM-owned content.

This supports the project requirement that WM should eventually be able to:
- rewrite quest arcs
- assign private rewards
- create alternate spell wrappers
- create item-gated abilities
- attach private dialogue and branching conversations

## Current reservation plan

### Spell slots / wrappers
- `900000` to `900999`
- Use for: private spell reward slots, wrapper spells, alternate ability variants

### Quest slots
- `910000` to `910999`
- Use for: private quest arcs, branch quests, follow-up quests, test quests

### Item slots
- `911000` to `911999`
- Use for: private reward items, equipped-gate items, item prototypes

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

This matches the design direction you wanted earlier:
- keep private content separate
- avoid collisions with normal server content
- allow a pool of dummy entries that WM can repurpose later

## Current implementation in repo

- `data/specs/reserved_id_ranges.json`
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

The next future step after this strategy is:
- create dummy row seeders for quest/item/spell/gossip/npc_text slots
- track which reserved slot is free, staged, or active
