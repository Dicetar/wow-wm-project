# WM pipeline skills

Repo-local agent skills (validated by `python scripts/validate_agent_skills.py`,
root `.agents/skills/`) that wrap the **existing** WM tooling for single pipeline
operations, so it gets found and used correctly instead of hand-rolled SQL/DBC
hacks. Each skill is self-contained; this index is just a map.

## These sit BENEATH the three contract skills — read those first
The fine-grained "how" skills below operate inside the rules defined by the
existing coarse contract skills. When they conflict, the contract skills win:

- **`wm-workflow`** — repo read-order, dirty-worktree discipline, the
  `WORKING`/`PARTIAL`/`BROKEN`/`UNKNOWN` status labels, smallest-useful-change loop.
- **`wm-content-release`** — the publish *contract*: feasibility tiers
  **T1** (server-only, visible via game state), **T2** (server + existing client
  assets), **T3** (client patch required), **T4** (client asset/UI work); the
  `python -m wm.content.release --plan/--packet` + `wm.content.preflight` gates;
  fresh-ID and rollback policy; retire dirty IDs in
  `data/specs/custom_id_registry.json` (don't recycle as free); read
  `docs/CONTENT_REQUIRED_FIELDS.md` before player-facing content.
- **`wm-live-bridge-lab`** — BridgeLab runtime: the `.bat` launchers, player
  scope (default `5406`, Broug `5405`), ports (MySQL `33307`, SOAP `7879`, world
  `8095`), the live-proof loop, dry-run-before-apply.

So, e.g.: `wm-create-spell-shell` is the concrete T3 path under
`wm-content-release`'s truth-split; `wm-grant-*` run inside
`wm-live-bridge-lab`'s scope/allowlist rules.

## Catalog (core CRUD batch)

| Skill | Operation | Wraps |
|---|---|---|
| `wm-create-quest` | author + publish a managed quest | `wm.quests.publish` + reserved-slot staging + `.reload all quest` |
| `wm-grant-quest` | push a quest into a character's log | `quest_add` bus action (`NativeApplier.insert_quest_add`) |
| `wm-create-item` | author + publish a managed item | `wm.items.live_publish` |
| `wm-grant-item` | push an item into a character's bags | `player_add_item` bus action |
| `wm-create-ability` | author a `wm.ability.v1` spec | `abilities/schema` (+ spell-shell + client-patch deps) |
| `wm-grant-ability` | grant an ability/aura to a character | `Grant-BridgeLabManagedSpell.ps1` / `compile_grant_plan`+`apply_grant_plan` |
| `wm-create-spell-shell` | make a server-known spell shell | `Stage-BridgeLabServerSpellDbc.ps1` (`wm.spells.server_dbc`) |
| `wm-build-client-patch` | client MPQ for spell icon/name/tooltip | `wm.spells.client_patch build` |

## Plumbing / safety batch

| Skill | Operation | Wraps |
|---|---|---|
| `wm-reload-worldserver` | hot-reload vs restart per data type | `SoapRuntimeClient` / `Restart-BridgeLabWorldServer.ps1` |
| `wm-reserve-slot` | reserve/stage/release a managed ID slot | `ReservedSlotDbAllocator` (Python API, no CLI) |
| `wm-rollback` | undo a managed quest/item/spell publish | `wm.{quests,items,spells}.rollback` / `Rollback-BridgeLabManagedSpell.ps1` |
| `wm-purge-quest-range` | bulk-remove a managed quest ID band | `wm.quests.purge_range` |

## WM-action batch

| Skill | Operation | Wraps |
|---|---|---|
| `wm-mark-for-attention` | activate a character for the WM (marker aura 946500) | `player_apply_aura` bus action |
| `wm-grant-character-state` | money / reputation / health / auras | implemented `player_*` bus actions |

## Domain + lifecycle batch

| Skill | Operation | Wraps |
|---|---|---|
| `wm-edit-live-quest` | edit a live quest's title/rewards in place | `wm.quests.edit_live` |
| `wm-remove-quest` | pull a quest from a character's log | `quest_remove` bus action |
| `wm-spawn-creature` | spawn/animate an NPC (implemented subset) | `creature_*` bus actions |
| `wm-auto-bounty` | run the reactive watcher / bounty lane | `Start-BridgeLabAutoBounty.ps1` |
| `wm-build-context-pack` | assemble the deterministic LLM input | `ContextPackBuilder` (Python API) |
| `wm-write-journal` | write/read/summarize narrative memory | `wm.journal.*` (Python API) |
| `wm-run-scene` | sequence a scripted scene | `SceneSequencer` (Python API) |

## Implemented-action gap batch (the last verified-working bus actions)

| Skill | Operation | Action |
|---|---|---|
| `wm-native-smoke-test` | confirm the bridge processes actions | `debug_ping` / `debug_echo` / `debug_fail` |
| `wm-remove-item` | take an item back from a character | `player_remove_item` |
| `wm-announce-to-player` | system message to a player | `world_announce_to_player` |
| `wm-random-enchant-item` | randomized enchant reward | `player_random_enchant_item` |

**Coverage:** every `implemented=True` bus action now has a skill. The remaining
73 registered action kinds are bridge-implementation work (see close-out below).

## Implemented vs registered native actions (important)

Many `player_*`/`creature_*` action kinds are **registered but NOT implemented** —
the bridge will not execute them, and a bus row just sits `pending`. Only actions
flagged `implemented=True` in `src/wm/sources/native_bridge/action_kinds.py` work
today. Verified-implemented player actions include: `player_apply_aura`,
`player_remove_aura`, `player_cast_spell`, `player_learn_spell`,
`player_unlearn_spell`, `player_set_display_id`, `player_add_money`,
`player_add_reputation`, `player_restore_health_power`, `player_add_item`,
`player_remove_item`, `player_random_enchant_item`. **NOT** implemented (do not
rely on): `player_add_xp`, `player_teleport`, `player_add_title`,
`player_add_achievement_credit`, `player_send_mail[_with_items]`,
`player_equip_item`, `player_create_bound_item`, phase/speed/resurrect/summon, etc.
Always check the flag before assuming an action works.

## Principles baked into these skills

- **Prefer the canonical `scripts/bridge_lab/*.ps1` wrappers** when one exists —
  they set the BridgeLab ports (DB **33307**, SOAP **7879**; `.env` defaults to
  the 3306 repack), back up files, and handle `-WaitForPlayerOnline`. Only drop
  to raw `python -m ...` / SQL when no wrapper covers the case.
- **Grants require the target GUID on `WmBridge.PlayerGuidAllowList`** (and
  `WmSpells.PlayerGuidAllowList` for spells/auras); the list is read at
  worldserver **startup**, so changes need a restart.
- **Spells are not hot-reloadable** — new `Spell.dbc` rows need a worldserver
  restart; quests hot-reload via `.reload all quest`; spell *behavior* tables
  (`spell_proc`/`spell_linked_spell`) hot-reload via SOAP.
- **Client visibility ≠ server function.** A custom spell/item works server-side
  without a client MPQ patch, but shows a broken icon/tooltip until patched. The
  running `wow.exe` locks `patch-z.mpq` — close it before installing.
- **No stock-ID carriers, no server-only player-facing spells** — see
  `docs/adr/0001-no-stock-live-spell-carriers.md` and
  `docs/adr/0003-client-shell-bank-for-visible-wm-spells.md`.

## Catalog close-out: what is NOT skillable (verified against `implemented` flags)

The original catalog optimistically marked many ops `[have]`. Verifying
`src/wm/sources/native_bridge/action_kinds.py` shows the bridge does **not**
implement these — a bus row for them just sits `pending`, so no honest skill
documents them as working until the native bridge implements them:

- **GameObject** — `gameobject_spawn` / `despawn` / `set_state` / template: **none
  implemented**. No gameobject skill.
- **Quest complete/turn-in** — `quest_complete` / `quest_complete_objective` /
  `quest_reward`: not implemented. The player completes quests in-game; only
  `quest_add` (grant) and `quest_remove` are bus-doable.
- **Item delivery extras** — `player_equip_item`, `player_create_bound_item`,
  `player_send_mail[_with_items]`: not implemented (so no offline mail / equip /
  bound-item grant). Item grant = `player_add_item` to an online player only.
- **Character rewards** — `player_add_xp`, `player_add_title`,
  `player_add_achievement_credit`, `player_teleport`, `player_set_phase` /
  `set_speed` / `resurrect` / `summon_to_location`: not implemented.
- **Creature control** — only spawn/despawn/display/scale/say/emote/cast are
  implemented; movement, faction, npc-flags, yell/whisper, attack/flee/evade,
  waypoints, react-state are **not**. `create-creature-template` (new NPC defs):
  partial.
- **build-item-client-patch** — the spell client-patch path exists
  (`wm-build-client-patch`); an analogous **item** icon MPQ path is not confirmed.

## Still code work, not doc-wrapping (point #3)
- **`llm-propose` LIVE** — the proposal adapter has a LIVE mode but the slice
  factories bootstrap it in **FIXTURE**; flipping to LIVE (LM Studio) is a code
  change, not a skill.
- **arc-runner** is internal slice machinery (`wm.arcs.runner`), driven by the
  panel/sentinel; not a standalone operator skill.

Everything in the catalog that maps to verified-implemented tooling now has a
skill; the rest is honestly enumerated above as bridge-implementation or
slice-wiring work.
