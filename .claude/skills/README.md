# WM pipeline skills

Thin Claude Code skills that wrap the **existing** WM tooling for single pipeline
operations, so it gets found and used correctly instead of hand-rolled SQL/DBC
hacks. Each skill is self-contained; this index is just a map.

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

## Not yet built (from the approved catalog)
Live-slice (LLM-propose LIVE, run-watcher, auto-bounty — likely need code wiring,
not just doc-wrapping), and other domains (creature/NPC spawn+control,
gameobject, scene, journal, character-state grants like money/xp/title/teleport,
mark-for-attention).
