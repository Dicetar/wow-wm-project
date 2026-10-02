Status: PARTIAL
Doc type: howto

# World Editing Tools

WM can now use the existing native bus to create persistent spawn points, move them, change respawn timing or phase, and delete them. Temporary creature/gameobject placement accepts exact `map_id`, `x`, `y`, `z`, and `orientation` as well as the existing player-relative placement. No new client patch is required for existing templates.

## Panel

Select a character in WM Session, then use the command catalog:

- **Nearby Persistent Spawns**: shows DB spawn IDs, coordinates, phases, and respawn seconds around fresh native online position. Use `position_source=saved` explicitly for last DB-saved/offline inspection; there is no silent fallback. Returned persistent rows do not prove actors are alive or phase-visible.
- **Scout World Ingredients**, **Search/Inspect World Templates**, and **Find Item Loot Sources**: reusable read-only discovery tools. See [World Ingredient Tools](WORLD_INGREDIENT_TOOLS.md).
- **Place or Edit World Spawn**: supply an action JSON and a unique `run_key`.
- **Publish and Trigger World Event**: supply a `wm.world.bundle.v1` JSON and a unique `run_key`.
- **Publish Managed Quest**: joins the existing item, spell, and shell publishers.
- **Change Quest Title**: uses the existing quest editing pipeline; accepted reward state is untouched.

## Placement And Editing

Example create payload: `control/examples/world_spawn_create.json`. Run:

```powershell
python -m wm.world.tools inspect --player-guid <guid> --radius 100
python -m wm.world.tools execute --player-guid <guid> --spec-json control/examples/world_spawn_create.json --run-key camp-1 --mode dry-run
python -m wm.world.tools execute --player-guid <guid> --spec-json control/examples/world_spawn_create.json --run-key camp-1 --mode apply --confirm-live-apply
```

Persistent operations use template faction and return `spawn_id`, the database GUID. They work on outdoor maps with the selected character online. Update/delete operate on a loaded spawn on that character's map, including stock spawns. They do not delete creature/object templates. Use a concrete world-change `reason`, such as player consequences, replacement content, or an event.

```json
{"action_kind":"world_spawn_update","payload":{"object_type":"creature","spawn_id":12345,"respawn_seconds":30,"reason":"Reinforcements arrive faster during the siege"}}
```

Use `world_spawn_delete` with the same `object_type`, `spawn_id`, and `reason` to remove a spawn. To move one, add all three coordinates and optionally `orientation`. Omitted position/phase/respawn fields preserve existing values. Respawn timing is a delay after death/use, not a density multiplier; add multiple spawn points to increase density.

For temporary hostile enemies, use `creature_spawn` with `use_template_faction=true`. Omitting this retains the original friendly/player-faction behavior. Temporary lifetimes remain limited by the existing native implementation to 10 minutes.

Native nearby snapshots also expose persistent `spawn_id`, respawn delay, phase, orientation, and creature hostility. A temporary summon has `spawn_id=0`; use its WM-owned object/live GUID instead. Spoken creature-name resolution preserves the new placement and faction fields. The autoplay tool manifest lists the operator authoring commands separately from conversation verbs: this slice does not enable autonomous persistent world edits in the selected-scope director.

## Event Bundles

An event is an ordered bundle using existing tools. See `control/examples/world_event_bundle.json`.

```powershell
python -m wm.world.bundle --bundle-json control/examples/world_event_bundle.json --player-guid <guid> --run-key encounter-1 --mode dry-run
python -m wm.world.bundle --bundle-json control/examples/world_event_bundle.json --player-guid <guid> --run-key encounter-1 --mode apply --confirm-live-apply
```

Step kinds: `native` (`action_kind`, `payload`), `publish_quest`, `publish_item`, `publish_spell`, `publish_shell` (each takes either inline `draft` or `draft_json` relative to the bundle file), and `wait` (`seconds`). Inline drafts are saved beside the bundle/job in `bundle-drafts/` as authoring artifacts. Put publications before quest/item/spell grants. Quest drafts are authored with the existing quest draft/release tools; item/passive/shell drafts use `wm.content.workbench`. Publishing a spell does not build its client DBC/MPQ or implement a new combat mechanic: use the existing shell/native-behavior and client-patch tools for that.

Execution stops at the first failed step and returns completed-step results. It is not an atomic transaction: already-published content and completed actions remain. Native steps keep the same action identity when rerunning the same `run_key`; the existing coordinator can reject an already-applied step rather than resume it. Publications likewise use their existing publisher semantics and may reject an already-published slot. This version is not a resume engine. A new key starts a new event. Cleanup is an explicit native step or a separate bundle; this version does not schedule recurring events or automatically restore deleted stock spawns.

To address an object created earlier in the bundle, use `{"from_step":0,"field":"spawn_id"}` as the value of `spawn_id` (or `object_id`/`live_guid_low` for temporary spawns). The value comes from that step's actual native receipt. This supports create -> wait -> move/delete event sequences without guessing IDs. Dry-run labels these receipt-dependent steps `deferred`; it does not claim to have validated the future object.

## Deployment

Install the rebuilt `mod-wm-bridge` and apply `native_modules/mod-wm-bridge/data/sql/world/updates/2026_10_01_00_wm_bridge_spawn_actions.sql`. Existing scope and action policy still apply. Persistent actions are high-risk typed operations, not raw SQL or GM-command lanes.

Implementation is not yet built, tested, deployed, or live-proven. The example coordinates are authoring examples, not certified terrain placements. Dry-run native action previews do not prove landing terrain or a future publication-dependent grant; confirm those in the game after publishing.
