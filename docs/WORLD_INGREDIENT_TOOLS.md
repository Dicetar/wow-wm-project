Status: PARTIAL
Last updated: 2026-10-01
Doc type: howto / implementation status

# World Ingredient Tools

This slice adds reusable **read-only** discovery tools, not concrete quests, scripted events or new rewards. It extends the existing panel catalog and typed director boundary. No tests, builds, deployment, DB queries or in-game checks were run for this slice.

## Tools

| Panel command | Purpose |
| --- | --- |
| `world.ingredients.scout` | Fresh-position survey of NPC roles, hostile population clusters, material loot sources and chest-type objects |
| `world.templates.search` | Literal name search over existing creature, gameobject, item, quest or named WM shell identities |
| `world.templates.inspect` | Identity fields, regional spawn counts/sample coordinates, existing quest starter/ender relations or shell metadata |
| `world.loot.sources` | Reverse lookup from an item through direct/reference loot into creature, skinning and chest-template source regions |
| `world.spawns.inspect` | Exact persistent spawn IDs/coordinates/respawn settings around live position, or explicitly selected saved position |

These commands have no apply route. Template/loot lookup can run without an active player; local scouting and live spawn inspection require a selected character with fresh native presence. Scouting also needs the phase/inventory/profession fields introduced by the gathering slice.

## CLI

Examples use operator-provided variables and do not allocate content IDs:

```powershell
python -m wm.world.ingredients scout --player-guid $Guid --radius 1800 --limit 20
python -m wm.world.ingredients scout --player-guid $Guid --search $Name
python -m wm.world.ingredients lookup --kind creature --search $Name
python -m wm.world.ingredients lookup --kind item --entry $ItemEntry
python -m wm.world.ingredients lookup --kind shell --search $AbilityName
python -m wm.world.ingredients loot --entry $ItemEntry --map-id $MapId
python -m wm.world.tools inspect --player-guid $Guid --position-source live
python -m wm.world.tools inspect --player-guid $Guid --position-source saved
```

Lookup kinds are `creature`, `gameobject`, `item`, `quest`, `shell`. Name search is literal text, not SQL or wildcard syntax. Shell lookup reads named repo definitions: a generic unassigned family slot is not an implemented ability. It does not establish native/client readiness or grant anything.

## Natural-Language Reads

The existing selected-scope director can now emit `inspect_world`, alongside its prior decision outcomes. Its three bounded read capabilities are:

```json
{"outcome":"inspect_world","capability":"world_scout","args":{"radius":1000,"limit":12},"reason":"Inspect nearby ingredients","question":""}
```

`world_lookup` takes `kind` plus a literal `search` or known `entry`. `loot_sources` takes an item `search` or known `entry`, with optional `map_id`. Host code resolves names, reads existing records and returns a compact evidence result to the normal chat voice. Multiple item-name matches return `ambiguous`; they do not silently pick the first item. The voice is instructed to state relevant unknowns and ask which item was intended. Information replies discard incidental mutation intents.

Examples of intended requests: "Which questgivers are nearby?", "Where does this material drop?", "Find an existing creature template with this name", "What does this WM ability shell actually declare?" These are information requests, not permission to publish a quest or edit spawns.

This route is connected to in-game chat events and operator chat while the selected-scope durable director is enabled. Existing non-read operator chat handling is unchanged. Decisions use the existing intake ledger; lookup results travel through existing reply/job diagnostics, not a second execution authority. Read results are refreshed when read; the immutable decision is not a frozen claim that the world will stay unchanged. Any later mutation still needs its own compiled artifact and current-world recheck.

## Evidence And Cost

- Local scouting uses native online presence no older than fifteen seconds, not last character-save coordinates. Phase/profession context must be no older than thirty seconds. Installed native sensing/config prerequisites are described in [Material Delivery Quests](MATERIAL_DELIVERY_QUESTS.md).
- NPC flags expose questgiver/trainer/vendor/banker roles. Hostility is a race-faction hint from current faction tables, not a proof of reputation-sensitive runtime reactions.
- Population and source locations come from persistent spawn rows. Scout coordinates are cluster centroids and distances are to the nearest sampled spawn, not a certified placement point. Exact spawn inspection/template samples expose real row coordinates separately. Dead actors, terrain, navigation and object lock requirements are not inferred as working.
- Loot readers batch template entries, cache repeated references within a lookup and expand at most four reference levels. Cycles are omitted. Ordinary materials exclude quest-bound items; corpse/skinning scouting is level-filtered and skinning uses a conservative skill requirement. Chest objects remain scouting-only with unchecked interaction requirements.
- Forward material scouting excludes quest-required loot and non-normal loot modes. Chance hints include group/reference arithmetic but not conditions or repeated reference rolls; they are not promised drop rates. Reverse source inspection retains quest-required flags so callers can see the difference.
- Surveys sample at most eighty creature clusters, forty object clusters, one thousand resolved material rows, bounded loot batches and the requested output limit. Model results are compacted separately. Missing/truncated results are not proof a source does not exist. Reverse lookup covers corpse, skinning and chest loot, not every source such as fishing, crafting or vendors.
- Exact spawn inspection reports all nearby persistent phases; it does not label every returned spawn visible to the player. `saved` is an explicit offline inspection option, never a silent fallback.

## Remaining Work

Requested tests and live read/answer proof remain. Navigation, reputation-aware reactions, object lock/skill resolution, conditions evaluation, additional source types and a richer search index can extend these tools later. This slice deliberately does not add collection commissions, authored quests, new mechanics or autonomous world mutations.
