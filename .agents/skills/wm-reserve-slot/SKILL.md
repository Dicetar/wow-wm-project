---
name: wm-reserve-slot
description: Reserve / stage / release a managed ID slot in wm_reserved_slot before publishing a quest, item, or spell. Use this WHENEVER a publish step complains the reserved slot is missing or has status "free" (expected "staged"), or when you need to allocate a fresh managed ID. Triggers: "reserve an ID", "stage the slot", "preflight says reserved_slot status free", "allocate a quest/item/spell id", "release a reserved slot". This is the gate the create-* skills depend on.
---

# Reserve / stage a managed ID slot

The publish pipelines (`wm-create-quest`/`-item`/`-spell-shell`) gate on a
`wm_reserved_slot` row for the entity ID: it must be **`staged`** for a fresh
publish (the publisher flips it to `active` on success). This skill manages those
rows via `ReservedSlotDbAllocator`.

> There is **no CLI / wrapper** for this — it's a Python API only.

## Entity types
`EntityType` is the artifact kind: `"quest"`, `"item"`, `"spell"`. (Note: quest
slots in the demo range are pre-seeded as `free`; item/spell slots may not exist
yet and must be allocated first.)

## Stage an existing free slot (most common)
```python
import dataclasses
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.reserved.db_allocator import ReservedSlotDbAllocator
s = dataclasses.replace(Settings.from_env(), world_db_port=33307)   # BridgeLab
alloc = ReservedSlotDbAllocator(MysqlCliClient(), s)
slot = alloc.ensure_slot_prepared(entity_type="quest", reserved_id=910500)
print(slot.slot_status)   # -> "staged" (or "active" if already published)
```
`ensure_slot_prepared` is idempotent: it stages a `free` slot and leaves
`staged`/`active` ones unchanged.

## Allocate the next free slot (when you don't have a specific ID)
```python
slot = alloc.allocate_next_free_slot(entity_type="quest")   # -> reserved + staged
print(slot.reserved_id)
```
`peek_next_free_slot(entity_type=...)` previews without claiming.

## Transition / release
```python
alloc.transition_slot(entity_type="quest", reserved_id=910500, new_status="active")
alloc.release_slot(entity_type="quest", reserved_id=910500, new_status="free")  # free it again
```

## Gotchas
- Publish preflight `reserved_slot ... status free; expected staged` → run
  `ensure_slot_prepared` first.
- Item/spell slot row simply doesn't exist → `allocate_next_free_slot` or seed the
  row; quests are pre-seeded but items/spells in the demo range may not be.
- Wrong DB port → BridgeLab is **33307** (`world_db_port`); `.env` defaults to 3306.
