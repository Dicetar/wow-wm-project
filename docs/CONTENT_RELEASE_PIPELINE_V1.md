Status: PARTIAL
Last verified: 2026-04-30
Verified by: Codex
Doc type: reference

# Content Release Pipeline V1

This is the release workflow for WM-created quests, abilities, items, scenes, spawns, and environmental effects.

The goal is not more freeform generation. The goal is a small set of release lanes that are hard to misuse:

1. draft from a known schema
2. reserve fresh visible IDs
3. validate against the live schema
4. dry-run and inspect the exact output
5. apply through the owned publisher or typed native action
6. reload or restart the right runtime surface
7. prove in-game before changing status to `WORKING`

If a visible quest, item, spell, creature, or object ships wrong, retire that ID and release a fresh ID. Do not keep mutating the same visible ID until the client or player state disagrees with the database.

Repo validator:

- module: `src/wm/content/release.py`
- tests: `tests/test_content_release.py`
- examples:
  - `control/examples/content_releases/repeatable_bounty_template.json`
  - `control/examples/content_releases/one_shot_template.json`
- `control/examples/content_releases/story_arc_choice_template.json`
- `control/examples/content_releases/abilities/*.json`
- `control/examples/content_releases/items/*.json`
- `control/examples/content_releases/scenes/*.json`

Validate a release spec:

```powershell
$env:PYTHONPATH='src'
python -m wm.content.release control/examples/content_releases/story_arc_choice_template.json --summary
```

Render the release plan before any apply step:

```powershell
$env:PYTHONPATH='src'
python -m wm.content.release control/examples/content_releases/items/night_watchers_lens_power_template.json --plan --summary
python -m wm.content.release control/examples/content_releases/scenes/creature_marker_scene_template.json --packet --summary
python -m wm.content.release control/examples/content_releases/scenes/creature_marker_scene_template.json --write-packet-dir .wm-release-packets/creature-marker --summary
```

`--plan` is a gate renderer. It prints the ID policy, dry-run/apply commands, runtime-sync requirement, live proof requirement, and release notes for the validated schema. It does not write DB rows, queue native actions, stage DBC files, or mutate the client.

`--packet` is the one-command release artifact view. It includes validation, the release plan, schema-specific compiled artifacts, and the live-proof checklist. Current artifacts are:

- scene specs: `control.scene.v1`
- story arc specs: `wm.character_journey.seed.v1` plus branch-lock plan
- ability specs: matching ability shell roster entry
- item specs: managed item power contract

`--write-packet-dir` writes `release_packet.json` plus every compiled artifact into the target directory. It refuses to overwrite existing packet files unless `--force` is supplied.

Audit every release template in a directory:

```powershell
$env:PYTHONPATH='src'
python -m wm.content.release --audit-dir control/examples/content_releases --summary
```

`--audit-dir` validates every `*.json` spec under the directory and builds a release plan for each valid spec. It exits non-zero if any spec is invalid.

Build a deterministic release-candidate pack from an existing context pack:

```powershell
$env:PYTHONPATH='src'
python -m wm.candidates.release_pack --context-pack-json control/examples/release_candidates/murloc_forager_context_pack.json --summary
python -m wm.candidates.release_pack --context-pack-json control/examples/release_candidates/murloc_forager_context_pack.json --reserved-item-entry <fresh-item-entry> --base-item-entry <known-good-base-item-entry> --summary
python -m wm.candidates.release_pack --context-pack-json control/examples/release_candidates/murloc_forager_context_pack.json --write-candidates-dir .wm-release-candidates/murloc-forager --summary
python -m wm.candidates.release_pack --context-pack-json control/examples/release_candidates/murloc_forager_context_pack.json --reserved-item-entry <fresh-item-entry> --base-item-entry <known-good-base-item-entry> --write-candidates-dir .wm-release-candidates/murloc-forager --write-packets --write-test-manifest --summary
```

`wm.release_candidate_pack.v1` is non-mutating. It turns `wm.context_pack.v1` / `generation_input` into ready release specs for repeatable bounty, story arc, shell ability, and native scene lanes. Managed item power stays blocked by default, then becomes a validated `wm.item.release.managed_power.v1` candidate only when `--reserved-item-entry` and `--base-item-entry` are supplied. Every ready spec is validated through `wm.content.release` and has packet status `PACKET_READY`.

`--write-candidates-dir` writes `release_candidate_pack.json` and one `*.release.json` file for every ready candidate. Blocked lanes are kept in the pack but are not written as release specs; when the item ID flags are supplied, the managed item-power spec is written with the rest of the ready candidates. Add `--write-packets` to also write a `<candidate>.packet/` directory for each ready candidate with `release_packet.json` and its compiled artifacts. Add `--write-test-manifest` to write `release_test_manifest.json`, a consolidated BridgeLab proof checklist with preflight commands, per-candidate dry-run commands, packet artifact paths, and live proof criteria.

## Research Basis

Current repo/source facts used by this pipeline:

- `src/wm/quests/bounty.py`, `src/wm/quests/compiler.py`, and `src/wm/quests/publish/__init__.py` already provide the repeatable bounty lane.
- `src/wm/arcs/factory.py` provides the current personal-arc publisher shape, but the latest live Shadowmoon proof deliberately cloned a known-working quest row for visible reward safety.
- Local AzerothCore schema has quest chain fields in `quest_template_addon`: `PrevQuestID`, `NextQuestID`, `ExclusiveGroup`, `BreadcrumbForQuestId`, and `SpecialFlags`.
- Local AzerothCore schema has `RewardNextQuest` and `RewardChoiceItemID*` / `RewardChoiceItemQuantity*` on `quest_template`.
- `src/wm/sources/native_bridge/action_kinds.py` distinguishes implemented native verbs from future verbs. Implemented release verbs include player aura/cast/display, item add/remove/random enchant, quest add/remove, creature spawn/despawn/say/emote/cast/display/scale, announcement, context snapshot, and debug actions.
- `native_modules/mod-wm-bridge/src/wm_bridge_action_queue.cpp` still returns `not_implemented` for registered native verbs that have no executor, including current gameobject and weather verbs.
- `D:/WOW/WM_BridgeLab/src/azerothcore/src/server/game/Spells/SpellInfo.cpp` target declarations show the practical spell-targeting families: self/caster, unit target, friendly target, dest/source area, cone, random target, channel target, item/gameobject/corpse variants, and trajectory.

## Release Gates

Every content release uses these gates:

1. `candidate`: chosen from context pack, roadmap lane, or operator request.
2. `schema`: matched to one base schema below.
3. `id_reservation`: fresh reserved visible IDs claimed or previewed.
4. `draft`: JSON or Python draft created with no SQL/GM/shell mutation fields.
5. `preflight`: live DB schema, reserved-slot state, base-row/template existence, and player scope checked.
6. `dry_run`: exact SQL/actions/runtime-sync intent printed.
7. `apply`: publisher/action queue applies through owned code only.
8. `runtime_sync`: `.reload`, DBC stage, client patch install, or worldserver restart chosen explicitly.
9. `live_proof`: player sees the quest/reward/ability/spawn/effect in-game.
10. `status`: mark `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`; write retired IDs when needed.

The status rule is strict: repo tests plus DB apply is not `WORKING` for player-facing content. It is at most repo/build/DB `WORKING` and gameplay `PARTIAL` until live proof passes.

## Quest Base Schemas

### Repeatable Bounty

Use for reactive/repeatable kill work, including current bounties.

Contract:

```json
{
  "schema_version": "wm.quest.release.repeatable_bounty.v1",
  "quest_kind": "repeatable_bounty",
  "player_guid": 5406,
  "slot_policy": "fresh_reserved_or_existing_active_repeatable",
  "repeatable": true,
  "quest": {
    "quest_level": 70,
    "min_level": 68,
    "grant_mode": "npc_start",
    "template_defaults": {
      "SpecialFlags": 1
    }
  },
  "objective": {
    "kind": "kill",
    "target_entry": 0,
    "target_name": "",
    "kill_count": 6
  },
  "reward": {
    "money_copper": 0,
    "item_entry": null,
    "spell_id": null,
    "reputation": []
  }
}
```

Rules:

- Force repeatable semantics with `SpecialFlags |= 1`.
- Keep one objective shape unless a new compiler/test lane exists.
- Regrant requires the repeatable template bit and quest cache reload; do not rely on deleting rewarded rows as the main flow.
- If visible rewards changed after the player accepted or completed the old version, publish a fresh quest ID.

### One-Shot Quest

Use for standalone "done and done" quests. This is not a story arc. It has no quest graph, no branch state, and no linked follow-up requirement.

Contract:

```json
{
  "schema_version": "wm.quest.release.one_shot.v1",
  "quest_kind": "one_shot",
  "player_guid": 5406,
  "slot_policy": "fresh_reserved_required",
  "repeatable": false,
  "quest": {
    "quest_level": 70,
    "min_level": 68,
    "grant_mode": "npc_start",
    "template_defaults": {
      "SpecialFlags": 0
    }
  },
  "objective": {
    "kind": "kill_or_item_or_talk",
    "target_entry": 0,
    "target_name": "",
    "count": 1
  },
  "reward": {
    "kind": "money_item_spell_reputation_or_none",
    "fresh_visible_reward_ids_required": true
  },
  "links": []
}
```

Rules:

- `links` must be empty.
- Do not use `PrevQuestID`, `NextQuestID`, `RewardNextQuest`, or `ExclusiveGroup`.
- A one-shot can still reward an item or shell ability, but any permanent/exclusive reward must also be recorded in the character journey/reward instance tables.
- Failed visible one-shot releases are retired, not mutated in place.

### Story Arc

Use for personal arcs. An arc is a graph of linked quests plus journey state, not just a single quest with better text.

Contract:

```json
{
  "schema_version": "wm.quest.release.story_arc.v1",
  "quest_kind": "story_arc",
  "player_guid": 5406,
  "arc_key": "character_arc_key",
  "nodes": [
    {
      "node_key": "start",
      "quest_id": null,
      "quest_schema": "wm.quest.release.one_shot.v1",
      "fresh_reserved_required": true
    }
  ],
  "edges": [
    {
      "from": "start",
      "to": "next",
      "kind": "turn_in_unlocks"
    }
  ],
  "fork_groups": [
    {
      "group_key": "choose_one",
      "choice_node_keys": ["choice_a", "choice_b"],
      "lock_policy": "first_turn_in_locks_others"
    }
  ],
  "journey_updates": {
    "stage_key": "",
    "branch_key": "",
    "reward_instance": null
  }
}
```

Rules:

- Each node uses a fresh quest ID.
- Linear links can use `PrevQuestID`, `NextQuestID`, and/or `RewardNextQuest` only after dry-run shows the target schema supports those columns.
- Forks use `ExclusiveGroup` only when the desired behavior matches AzerothCore's quest exclusivity. For "first turned in wins", WM must also record the branch in character journey state and remove/fail active sibling choices through a typed native quest action once that verb is proven.
- Until native `quest_fail` is implemented, branch losers should be locked by eligibility and removed only through the proven `quest_remove` path when safe.
- Arc rewards must be recorded as reward instances. Quest reward visibility is a separate proof gate.

Compile the arc state and branch-lock workflow:

```powershell
$env:PYTHONPATH='src'
python -m wm.content.release control/examples/content_releases/story_arc_choice_template.json --emit-journey-plan
python -m wm.content.release control/examples/content_releases/story_arc_choice_template.json --emit-branch-lock-plan
```

`--emit-journey-plan` creates a strict `wm.character_journey.seed.v1` plan that can be dry-run through `python -m wm.character.journey apply --mode dry-run`. `--emit-branch-lock-plan` creates a non-mutating branch contract for "first completed choice wins": the winning quest turn-in records a journey branch and sibling active quests are removed through scoped `quest_remove` actions only after quest IDs, player scope, policy, and audit are proven. It never uses freeform GM commands and does not claim `quest_fail` behavior while that native verb remains unimplemented.

## Ability Shell Roster

The generic shell bank now fills the whole `946000-946999` roster with ten 100-slot cast-shape families:

| Ability type | Shell family | Range | Seed |
| --- | --- | ---: | --- |
| Targeted enemy projectile | `unit_target_projectile` | `946000-946099` | Fireball-style seed |
| Targeted friendly effect | `unit_target_friendly` | `946100-946199` | Flash Heal-style seed |
| Targeted enemy instant/effect | `unit_target_effect` | `946200-946299` | Faerie Fire-style seed |
| AOE centered on target | `target_centered_aoe` | `946300-946399` | Seed of Corruption-style seed |
| Ground-target AOE | `ground_target_aoe` | `946400-946499` | Rain of Fire-style seed |
| AOE centered on caster | `caster_centered_aoe` | `946500-946599` | Arcane Explosion-style seed |
| Self aura, stance, or toggle | `self_aura` | `946600-946699` | Arcane Intellect-style seed |
| Random eligible targets | `random_targets` | `946700-946799` | Starfall-style seed |
| Passive aura | `passive_aura` | `946800-946899` | passive aura seed |
| Frontal cone | `frontal_cone` | `946900-946999` | Cone of Cold-style seed |

Special compatibility families remain:

- `940000-940001`: summon-pet compatibility shells.
- `944000`: combat proficiency compatibility shell.
- `945000`: pet active compatibility shell.

Executable release schema:

```json
{
  "schema_version": "wm.ability.release.shell_power.v1",
  "content_kind": "ability",
  "player_guid": 5406,
  "ability_key": "template_targeted_projectile",
  "ability_type": "targeted_effect_with_projectile",
  "shell_family": "unit_target_projectile",
  "slot_policy": "fresh_shell_slot_required",
  "behavior_kind": "generic_projectile",
  "client_truth": {
    "client_patch_required": true,
    "server_dbc_required": true,
    "spellbook_button_required": true
  },
  "runtime": {
    "native_behavior_required": true,
    "python_decision_required": true,
    "audit_required": true
  },
  "seed": {
    "stock_seed_spell_id": 133,
    "seed_only": true
  }
}
```

The validator enforces:

- `ability_type` must match the correct `shell_family`.
- any explicit `shell_spell_id` must belong to that shell family.
- stock spell IDs are allowed only under `seed` with `seed_only=true`.
- shell-backed abilities must declare client patch truth and native runtime ownership.
- chain, channel, and movement spells are behavior variants over existing shell families until a release needs exact dedicated client UX.
- gameobject, corpse, vehicle, profession, and item-target enchant abilities are rejected from this shell release lane until their specialized pipeline exists.

Validate an ability template:

```powershell
$env:PYTHONPATH='src'
python -m wm.content.release control/examples/content_releases/abilities/targeted_projectile_template.json --summary
```

Inspect shell coverage for all supported, variant, and blocked ability concepts:

```powershell
$env:PYTHONPATH='src'
python -m wm.content.release --ability-roster --summary
```

Ability release rule:

1. Pick the smallest shell family that matches client targeting/presentation.
2. Keep stock spells as seed/template/visual IDs only.
3. Bind the WM shell to a native behavior kind or managed spell row.
4. Stage server DBC if the spell must be learnable/castable server-side.
5. Install client patch if the player must see spellbook/action-bar text/icon/targeting.
6. Prove the actual in-game button, cast shape, range, visible aura/impact, cooldown, and revoke path.

## Spell Types Not Yet Dedicated Families

Some spell concepts should not get a new shell family until a release needs exact client UX:

| Spell concept | Current release lane |
| --- | --- |
| Chain/jump spells | Use targeted projectile/effect shell plus native behavior, unless chain UI/tooltip/visual is required. |
| Channeled drains/beams | Use targeted effect/projectile shell plus native cast-state behavior; add a dedicated channel family only if client channel presentation matters. |
| Channeled ground storms | Use `ground_target_aoe` plus behavior duration. |
| Charge/leap/blink/movement | Native movement behavior plus target/dest shell as needed; do not fake movement through stock carriers. |
| Summon guardian/temp minion | Use summon compatibility now, or add a summon-guardian family later if multiple visible summon buttons need separate client UX. |
| Item-target, enchant, weapon imbue | Prefer managed item/on-use/equip pipeline. Add an item-target spell family only for a player-facing spellbook button. |
| Gameobject target | Future specialized family; current native gameobject mutation verbs are not implemented. |
| Corpse/resurrection/skin/mining target | Future specialized family; reject generic release until a concrete product use exists. |
| Vehicle/passenger/control | Future native/runtime feature, not a generic shell-bank default. |
| Profession/tradeskill recipes | Future profession pipeline, not a combat spell shell. |

## Item Release Lane

Use `Item Slot Pipeline V1` unless a stronger item-specific publisher exists.

Rules:

- Clone a known-good base item row.
- Override only controlled fields: name, description, display, quality, level, binding, stats, spell slots, stack limits, and prices.
- Hidden item effects need visible state: aura, buff, debuff, tooltip, combat message, or spawned object.
- Item-granted abilities should prefer a visible item spell or an equipped-state gate over silent native mutation.
- Quest reward integration uses a fresh quest ID when reward visibility changes.
- Rollback must report both DB state and player-copy cleanup limits.

Executable managed item power schema:

```json
{
  "schema_version": "wm.item.release.managed_power.v1",
  "content_kind": "item",
  "player_guid": 5406,
  "item_key": "template_night_watchers_lens_power",
  "item_entry": 910006,
  "slot_policy": "existing_proven_item_slot_extension",
  "visibility": {
    "player_visible_state_required": true,
    "tooltip_required": true,
    "wearer_aura_spell_id": 132,
    "target_aura_spell_id": 770
  },
  "runtime": {
    "native_behavior_required": true,
    "audit_required": true,
    "rollback_required": true
  },
  "reward_integration": {
    "quest_reward_allowed": true,
    "fresh_quest_required_when_reward_changes": true,
    "direct_grant_allowed": true,
    "cleanup_supported": true
  },
  "effects": [
    {
      "effect_key": "spell_focus",
      "kind": "direct_spell_damage_bonus",
      "trigger": "non_wand_direct_spell_damage",
      "target": "marked_enemy",
      "visible_state": "target aura 770 from the Lens wearer",
      "native_hook": true,
      "amount_pct": 15
    }
  ]
}
```

The validator enforces:

- managed item powers have tooltip text and visible wearer/target state
- hidden combat/stat/proc/companion effects name their visible gating state
- hidden effects require explicit native hooks
- quest reward changes require a fresh quest ID
- native behavior, audit, and rollback are mandatory for item powers

Validate item power templates:

```powershell
$env:PYTHONPATH='src'
python -m wm.content.release control/examples/content_releases/items/night_watchers_lens_power_template.json --summary
```

## Creature And Scene Release Lane

Use typed native actions and WM-owned world-object records for temporary actors.

Current proven creature verbs:

- `creature_spawn`
- `creature_despawn`
- `creature_say`
- `creature_emote`
- `creature_cast_spell`
- `creature_set_display_id`
- `creature_set_scale`

Rules:

- Spawn only WM-owned temporary creatures unless a permanent creature template/spawn publisher is added.
- Every follow-up action must resolve a WM-owned `object_id`, GUID, or `arc_key`.
- Use `duration_ms` or an explicit cleanup step.
- Do not mutate arbitrary nearby creatures.
- Combat behavior belongs in native code when it must be reliable.

Executable scene release schema:

```json
{
  "schema_version": "wm.scene.release.native_sequence.v1",
  "content_kind": "scene",
  "player_guid": 5406,
  "scene_key": "template_creature_marker_scene",
  "scene_type": "creature_marker",
  "slot_policy": "no_visible_id_required",
  "trigger": {
    "kind": "manual_operator",
    "source_event_required": false
  },
  "runtime": {
    "native_actions_required": true,
    "audit_required": true,
    "player_scope_required": true,
    "control_scene_required": true
  },
  "steps": [
    {
      "step_key": "spawn",
      "native_action_kind": "creature_spawn",
      "payload": {
        "creature_entry": 920101,
        "arc_key": "scene:{scene_id}:{player_guid}:{run_key}",
        "duration_ms": 15000
      },
      "risk_level": "medium",
      "idempotency_suffix": "spawn",
      "requires_live_proof": true
    }
  ],
  "cleanup": {
    "required": true,
    "expires_seconds": 30,
    "steps": [
      {
        "step_key": "despawn",
        "native_action_kind": "creature_despawn",
        "payload": {
          "arc_key": "scene:{scene_id}:{player_guid}:{run_key}"
        },
        "risk_level": "medium",
        "idempotency_suffix": "despawn",
        "requires_live_proof": true
      }
    ]
  }
}
```

The validator enforces:

- every scene step uses a registered, implemented, release-allowed native verb
- `creature_spawn` has an owned cleanup path with `creature_despawn`
- all steps have stable `step_key` and `idempotency_suffix`
- every step is marked as needing live proof before `WORKING`
- event-driven scenes require a source event and max event age
- `gameobject_*` and `zone_*weather*` actions are rejected until their native executors are implemented and live-proven

Validate scene templates:

```powershell
$env:PYTHONPATH='src'
python -m wm.content.release control/examples/content_releases/scenes/creature_marker_scene_template.json --summary
python -m wm.content.release control/examples/content_releases/scenes/creature_marker_scene_template.json --emit-control-scene
python -m wm.content.release --scene-action-roster --summary
```

`--emit-control-scene` converts an approved scene release spec into strict `control.scene.v1` JSON for the existing `python -m wm.control.scene_play` dry-run/apply workflow. It does not execute anything by itself.

`--scene-action-roster` reports which native action verbs are currently release-allowed for scenes and which registered verbs are blocked as future work. Current blocked future scene verbs include `gameobject_spawn`, `gameobject_despawn`, `gameobject_set_state`, `zone_set_weather`, and `zone_clear_weather_override`.

## Events And Director Lane

Events are evidence, not mutation authority.

Use this flow:

1. Native bridge observes an event and writes server truth.
2. Python projects it into canonical WM event/journal state.
3. Context pack explains eligibility and recent history.
4. Control proposal picks a typed action or publisher.
5. Policy rejects stale, wrong-player, duplicate, or unsupported proposals.
6. Native action queue executes fixed verbs and returns result JSON.
7. Audit links source event, proposal, native request, and result.

Scene releases should be built from `control.scene.v1` steps with `idempotency_suffix` on each action. No scene should require freeform SQL, GM commands, or raw shell commands.

## Gameobjects And Weather

These are not ready as generic release lanes yet.

Current status:

- Native sensing sees gameobject interactions and loot sources.
- `gameobject_spawn`, `gameobject_despawn`, and `gameobject_set_state` are registered in policy seeds but not implemented in the native executor.
- `zone_set_weather` and `zone_clear_weather_override` are registered in policy seeds but not implemented in the native executor.
- Weather is probably zone/global state in practice, not a clean per-character illusion, unless a future native implementation scopes it carefully through phase/area/player-visible tricks.

Release rule:

- For deployables today, use a WM-owned creature with a model/scale/display and explicit cleanup.
- For weather today, use announcements, auras, scene actors, or local visual spells. Do not claim real weather control until `zone_set_weather` is implemented and live-proven.
- When gameobject/weather verbs are implemented, they need the same ownership, duration, rollback, and player-scope gates as creature scenes.

## Foolproof Release Checklist

Before apply:

- Fresh visible IDs are reserved or the feature explicitly reuses a proven active repeatable slot.
- The draft has no `sql`, `gm_command`, `shell_command`, or mutation escape hatch fields.
- The live DB schema has every column the compiler intends to write.
- Client truth is identified: no patch, existing asset only, DBC shell patch, or full client asset/UI work.
- Runtime sync is named: reload, DBC stage, MPQ install, restart, or no safe reload.
- Rollback/retire plan is written before apply.

After apply:

- Inspect DB rows.
- Reload/restart the exact runtime surface.
- Test on player `5406` unless another scoped player is explicitly selected.
- Confirm visible player-facing behavior.
- Update docs/status and retired IDs.
- Leave status `PARTIAL` when any live proof is missing.
