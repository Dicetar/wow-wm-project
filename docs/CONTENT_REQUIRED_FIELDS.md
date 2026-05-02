Status: WORKING
Last verified: 2026-05-02
Verified by: Codex
Doc type: reference

# Content Required Fields

This is the pre-deploy checklist for WM quests, items, and abilities. It exists because recent live Broug work exposed avoidable field omissions: invisible gameobjects, creature templates without model rows, vague quest objective text, self-cast spells inheriting range, WM auras inheriting stock spell-family stack identity, stale client payloads, and scoped native scripts failing because the test player was not allowlisted.

If any required field below is missing, the release is `PARTIAL` at best and should not be handed to the player as ready.

## Universal Requirements

Every player-facing content change must record:

- fresh ID claims in `data/specs/custom_id_registry.json`
- a source SQL or JSON artifact in the repo, not only a live DB hotfix
- `wm_reserved_slot` rows for every custom quest, item, spell, creature, gameobject, and hidden-credit entry
- explicit player scope when content is character-specific
- runtime sync plan: reload command, DBC stage, client patch install, or worldserver restart
- proof label: `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`

Do not reuse a dirty visible ID after the client or player has seen a broken version.

## Quest Required Fields

For each quest row:

- `ID`: fresh claimed quest ID.
- `LogTitle`: final player-facing title.
- `LogDescription`: concrete action text only. Include target names, counts, map/zone clue, and coordinates when custom content is involved.
- `QuestDescription`: lore/fluff only. Do not hide operational instructions here.
- `QuestCompletionLog`: where to turn in or what final action remains.
- `ObjectiveText*`: concrete objective labels matching the required objective columns.
- `RequiredNpcOrGo*` and `RequiredNpcOrGoCount*`: correct sign and count. Creature IDs are positive; gameobject IDs are negative.
- `RewardItem*`, `RewardAmount*`, `RewardDisplaySpell`, `RewardSpell`, `RewardMoney`, and reward text: explicitly set or explicitly cleared.
- `quest_template_addon`: `PrevQuestID`, `NextQuestID`, and `SpecialFlags` when chaining or repeatability matters.
- `quest_request_items` and `quest_offer_reward`: completion and reward text.
- starter and ender rows: `creature_queststarter` / `creature_questender` or gameobject equivalents.

For every objective target:

- Verify faction/hostility for kill targets.
- Verify live spawn count, map, phase, and respawn. Do not require 8 kills from a single rare/one-off spawn unless that is intentional and tested.
- For custom creatures, insert both `creature_template` and `creature_template_model`; this core rejects custom creatures without model rows.
- For custom gameobjects, insert both `gameobject_template` and `gameobject` spawn rows with visible `displayId`, `phaseMask`, `spawnMask`, and reachable coordinates.
- For clickable quest gameobjects, use a valid GOOBER-style template: `type=10`, nonzero `displayId`, quest binding in `Data1`, and cast time in `Data3`.

Recent failures that this gate prevents:

- Ash-Worn Track Circle `195500` had `displayId=0` and no quest GOOBER data, so it existed but was invisible/useless.
- Wei Jin `915500` and V2 actors had `creature_template` rows but no `creature_template_model` rows, so worldserver refused to load/spawn them.
- `910185` put vague trial wording in `LogDescription`; the upper quest log must say exactly what to kill and where.

## Item Required Fields

For each custom item:

- `entry`: fresh claimed item ID.
- `base_item_entry`: known-good row to clone from `item_template`.
- `name`, `description`, `displayid`, `Quality`, `ItemLevel`, `RequiredLevel`.
- `class`, `subclass`, `InventoryType`, `bonding`, `maxcount`, `stackable`.
- `AllowableClass` and `AllowableRace`: set intentionally, usually unrestricted for WM consumables.
- inherited stats and spells: clear every unused `stat_type*`, `stat_value*`, `spellid_*`, `spelltrigger_*`, `spellcharges_*`, `spellcooldown_*`, and category field.
- on-use items: `spellid_1`, `spelltrigger_1=0`, charges, item cooldown, and category cooldown set deliberately.
- native items: `ScriptName` set and matching C++ `ItemScript` registered in the module loader.
- hidden runtime effects: visible player-facing aura, debuff, combat message, or tooltip explaining the effect.
- quest/vendor/loot source: how the player actually receives it.
- rollback snapshot and `wm_reserved_slot` row.

For scoped native items, also verify:

- the intended player GUID is in `WmBridge.PlayerGuidAllowList` or DB scope
- the item script returns a clear player message when scope blocks use
- the module was rebuilt/restarted after C++ changes

Recent failure this gate prevents:

- Energy Surge Potion `910014` appeared broken for Broug because the native ItemScript was scoped and the runtime allowlist/config must include the test player before live proof.

## Ability Required Fields

For each player-facing WM ability:

- fresh shell ID in the correct shell family.
- shell-bank entry in `control/runtime/spell_shell_bank.json`.
- client manifest entry in `client_patches/wm_spell_shell_bank/manifest.json`.
- `wm_spell_shell` row with `ShellSpellID`, `ShellKey`, `FamilyID`, `Label`, `ClientPatchVersion`, and ownership.
- `wm_spell_behavior` row with exact `BehaviorKind`, typed config, and status.
- native behavior implementation and hook coverage in `mod-wm-spells`.
- `spell_script_names` dispatch row for active buttons that use shell dispatch.
- `spell_cooldown_overrides` for active buttons with cooldown/GCD behavior.
- grant path scoped to the intended character: `character_spell` plus `wm_spell_grant`, normally from quest-complete hooks.
- server DBC staged after presentation changes.
- client MPQ rebuilt/installed after presentation changes.
- worldserver restarted when DBC/native/template cache needs reload.

DBC/client presentation required fields:

- name, tooltip, and icon match the mechanic.
- `spellbook_seed_spell_id` and `spellbook_ability_id` when the spell must appear in the spellbook.
- `power_type`, cost, cooldown, category cooldown, `start_recovery_time`, and GCD category.
- `duration_index`, `stack_amount`, aura type, and target fields for visible buffs/debuffs.
- `range_index` must match targeting. Learned self-cast active buttons must set `range_index=1`; do not inherit a 30 yd friendly range from the Arcane Intellect self-aura seed.
- `effect_implicit_target_a_*` must match targeting. Self-cast buttons use self/caster targeting, not unit target targeting.
- marker auras cloned from stock buffs must clear inherited stack identity unless explicitly intended: `spell_family_name=0`, `spell_family_flags_1=0`, `spell_family_flags_2=0`, `spell_family_flags_3=0`, `damage_class=0`, and `prevention_type=0`.
- clear inherited weapon/class/interruption fields when the seed spell does not match the mechanic.
- visible state shells must be harmless markers when native runtime owns the real behavior.

## WM Aura Isolation Gate

This gate is mandatory for every WM-owned visible buff/debuff shell cloned from a stock aura seed such as Arcane Intellect.

Stock spell rows carry hidden stacking and category identity through DBC fields, not only through the visible spell ID. If two unrelated WM marker auras inherit the same stock family data, the core may treat them as mutually exclusive or related effects. That can make one mechanic remove another mechanic's aura even when the WM IDs are fresh and separate.

Required default for harmless WM marker auras:

- `spell_family_name=0`
- `spell_family_flags_1=0`
- `spell_family_flags_2=0`
- `spell_family_flags_3=0`
- `damage_class=0`
- `prevention_type=0`

Only keep nonzero family/category fields when the mechanic deliberately wants stock-family interaction, and then add an explicit test naming that interaction.

Live regression that proved this rule:

- Energy Surge `946606` and Killing Intent `946620` were separate WM IDs, but both inherited Arcane Intellect's Mage family flags. Cloud Step applying/removing Killing Intent could remove the Energy Surge Potion aura. The fix was not another new ID; it was clearing inherited family identity in both server and client DBC.

Runtime required fields:

- native code gates behavior on the live visible aura/debuff/state when the behavior is player-facing.
- hostile/friendly/dead/LOS/range/root/stun/resource/cooldown failures return cleanly.
- cooldown refunds or extensions update both WM runtime state and the core/client cooldown table. For learned buttons, reducing only a custom timestamp is not enough; use the core cooldown API so the spellbook/action-bar cooldown changes in-game.
- state cleanup on logout, death, map unload, aura loss, and quest/reward revocation.
- counters or proof rows for new mechanics.
- no mutation of unrelated systems unless explicitly part of the plan.

Recent failures this gate prevents:

- Qi Reversal `946621` was a self-cast cleanse but inherited the seed spell's range display because `range_index=1` was missing.
- Energy Surge `946606` and Killing Intent `946620` both inherited Arcane Intellect's Mage spell family flags; Cloud Step/Killing Intent could therefore remove the potion aura through core aura stacking.
- Cloud Step initially had stale client/server payload and reward-grant holes, so the spellbook and quest reward truth diverged.
- Marked Meridian initially had visible state without working native consumption, so aura visibility was not enough proof.

## Required Pre-Deploy Checks

Before handing content to the player, run focused static checks for:

- ID freshness and registry claims.
- no forbidden ID reuse.
- quest objective text contains concrete directions, not only lore.
- custom creatures have model rows.
- custom gameobjects have visible display and quest data.
- self-cast learned active spells have self range.
- WM marker auras do not inherit stock spell-family flags unless the stacking rule is intentional and tested.
- client and server DBC payloads contain the same presentation fields.
- native allowlists include the test player for scoped bridge/spell behavior.

Then run live proof:

- accept the quest from the intended starter
- complete every objective without GM help
- turn in and confirm reward panel/learned spell/item
- use the item or spell from the normal client UI
- verify combat/resource/quest counters
- restart/relog once and confirm persistence or cleanup behavior
