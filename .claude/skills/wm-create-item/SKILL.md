---
name: wm-create-item
description: Author and publish a new managed item into the WM world DB. Use this WHENEVER a custom item must exist on the server — a quest reward, a managed power item, a starter token, or any item the WM hands out. Do NOT hand-write item_template SQL; this pipeline validates, snapshots for rollback, publishes, and reloads. Triggers: "create an item", "make a managed item", "publish an item", "I need a custom reward item / token".
---

# Create a managed item

Publishes a new item through `wm.items.live_publish` — the project's item
pipeline. It validates the draft, writes a rollback snapshot + publish log,
inserts the `item_template` row (cloning a sane base item for sensible
defaults), and reloads. **Never** hand-roll `item_template` SQL.

## Prerequisites
- A managed item **entry** in a reserved range (e.g. a story module's
  `id_ranges.item`). Stage its reserved slot first (same pattern as quests:
  `ReservedSlotDbAllocator(...).ensure_slot_prepared(entity_type="item", reserved_id=<entry>)`).
- A **base item entry** to clone defaults from (`base_item_entry`).
- BridgeLab DB on **33307**, SOAP on **7879**.

## Steps

### 1. Write the draft JSON
Under `control/examples/items/<name>.item.json`. Core `ManagedItemDraft` fields:
```json
{
  "item_entry": 910500,
  "base_item_entry": 6948,
  "name": "Humming Token",
  "description": "It will not stop humming.",
  "quality": 1,
  "inventory_type": 0,
  "required_level": 1,
  "bonding": 1,
  "max_count": 1,
  "stackable": 1
}
```
(See `control/examples/content_releases/items/fresh_item_power_template.json` and
`src/wm/items/models.py::ManagedItemDraft` for the full field set, including stat
and on-use spell blocks.)

### 2. Dry-run, then apply (with SOAP reload)
```bash
WM_WORLD_DB_PORT=33307 WM_CHAR_DB_PORT=33307 WM_SOAP_PORT=7879 \
  python -m wm.items.live_publish --draft-json control/examples/items/<name>.item.json --mode dry-run --summary
WM_WORLD_DB_PORT=33307 WM_CHAR_DB_PORT=33307 WM_SOAP_PORT=7879 \
  python -m wm.items.live_publish --draft-json control/examples/items/<name>.item.json --mode apply --runtime-sync soap --summary
```
Look for `applied: true`, validation/preflight ok.

### 3. Verify
```sql
SELECT entry, name, Quality, InventoryType FROM item_template WHERE entry = 910500;
```

## Client visibility (IMPORTANT)
The server now knows the item, but a **custom icon / name / description only
renders correctly in the client with an MPQ patch**. A purely server-side item
shows up but may have a wrong/placeholder icon and tooltip. If the item needs a
custom icon, that's a separate client-patch task (see the spell client-patch
tooling under `wm.spells.client_patch` for the analogous pattern) — flag it,
don't pretend the tooltip is correct.

## Then what
To put the item in a character's bags, use **wm-grant-item**.

## Gotchas
- Skipped reload → grant fails because the worldserver doesn't know the entry.
- Custom icon looks wrong in-client → needs the MPQ patch, not a server fix.
