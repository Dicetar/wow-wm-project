Status: WORKING
Last verified: 2026-05-01
Verified by: user + Codex
Doc type: reference

# WM Working Strategies V1

This is the compact reference for strategies that have survived live feature work. It is not a design wishlist and not a transcript summary.

Use it with:

- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)
- [Content Release Pipeline V1](CONTENT_RELEASE_PIPELINE_V1.md)
- [Broug Guard Pipeline V1](BROUG_GUARD_PIPELINE_V1.md)
- [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)
- [Custom ID Ledger](CUSTOM_ID_LEDGER.md)

## Baseline Rules

These rules apply to every new feature:

- Fresh visible IDs are mandatory for new or corrected visible content. If a quest, spell, item, creature, object, or client-visible row shipped wrong, retire it and publish a replacement on a fresh ID.
- Python owns decisions, validation, publishing, rollback, branch state, reward instances, and audit.
- Native owns sensing, fixed typed actions, combat hooks, runtime effects, and shell-bound behavior.
- Client truth and server truth are separate gates. A visible ability needs both a client patch row and a server-known castable row.
- No freeform SQL, GM command, shell command, or direct LLM mutation lane is a product path.
- Status is not `WORKING` until live player-facing proof passes. Repo tests plus DB rows are only repo/build/DB proof.

## Local Search Tooling

On this machine, bare `rg` can resolve to the bundled Codex app copy:

```text
C:\Program Files\WindowsApps\OpenAI.Codex_...\app\resources\rg.exe
```

That binary can fail with `Access is denied`.

Use the repo-local ripgrep binary instead:

```powershell
.\.wm-bootstrap\tools\ripgrep\rg.exe -n "pattern" docs src native_modules control tests
```

The fallback copy also exists at:

```powershell
.\.wm-tools\rg.exe
```

Do not interpret bare `rg` failure as "no matches." If both local binaries are missing, use `Get-ChildItem ... | Select-String` and record the tooling gap.

## Player Scoping

Use the marker aura workflow when the active character GUID is unknown.

Working marker:

- spell: `946602`
- name: `WM Watcher Beacon`
- behavior: undispellable, no-duration, no gameplay effect
- purpose: native bridge aura sensor discovers the real logged-in character
- stock fallback: `132` only for compatibility

Discovery flow:

```powershell
python -m wm.sources.native_bridge.configure --config-path D:\WOW\WM_BridgeLab\run\configs\modules\mod_wm_bridge.conf --allow-all --reload-via-soap --summary
python -m wm.sources.native_bridge.player_marker scan --spell-id 946602 --since-seconds 300 --summary
python -m wm.sources.native_bridge.player_marker scope-latest --spell-id 946602 --since-seconds 300 --summary
python -m wm.sources.native_bridge.configure --config-path D:\WOW\WM_BridgeLab\run\configs\modules\mod_wm_bridge.conf --clear --reload-via-soap --summary
```

Wildcard observation is only for discovery. After scoping, return to DB-backed player scope and start the normal watcher for that one player.

## Quest Strategies

### Repeatable Bounties

Use repeatable bounties for reactive kill loops.

Working strategy:

- compile from a strict bounty schema
- force repeatability through `quest_template_addon.SpecialFlags |= 1`
- prefer explicit bounty templates for operator tests
- use fresh quest IDs unless reusing a proven active repeatable slot on purpose
- reload quest templates after apply
- prove grant, completion, reward, suppression, cooldown, and regrant before calling the full loop `WORKING`

Do not make repeatability depend on manually deleting rewarded rows. That is a recovery move, not the pipeline.

### One-Shot Quests

Use one-shot quests for standalone "done and done" content.

Working definition:

- no linked follow-up quest
- no fork state
- no branch lock
- no `PrevQuestID`, `NextQuestID`, `RewardNextQuest`, or `ExclusiveGroup`
- one fresh quest ID
- one visible completion outcome

A one-shot can reward an item, ability, money, reputation, or nothing. If the reward is permanent or exclusive, also record it through the character journey/reward-instance system.

### Story Arcs

Story arcs are linked quest graphs plus WM journey state. They are not one-shot quests with better text.

Working strategy:

- every visible node gets its own fresh quest ID
- linear arcs can use core link fields when the schema supports them
- branch arcs need WM journey state in addition to any core exclusivity field
- "first turned in wins" means the first completed choice records the branch, then sibling choices become ineligible or are removed through a proven typed quest action
- rewards are recorded as reward instances; quest reward-panel visibility is still a separate live proof gate

Use `ExclusiveGroup` only when AzerothCore's native behavior matches the desired fork. Do not claim loser failure behavior until the native remove/fail action for that shape is implemented and proven.

### Custom Mechanic Objectives

For abilities that count nonstandard events, do not fake the objective with broad stock kills.

Working Broug strategy:

- hidden creature credit entries represent visible quest objectives:
  - `920104`: Impossible Guard parry credit
  - `920105`: Deflect credit
- native runtime owns the real counter:
  - `wm_broug_guard_counter.CounterKey = 'universal_parry'`
  - `wm_broug_guard_counter.CounterKey = 'deflect_success'`
- native quest-complete hooks learn the reward shell only for the completing character
- reward hooks insert active `wm_spell_grant`
- no class default, playerbot, or global grant path exists

This is the right shape for future "do a custom thing 1000 times" quests.

## Ability Strategies

### Shell Selection

Pick the shell family from the client behavior the player needs, not from a convenient stock spell.

Working shell families:

- targeted projectile: `946000-946099`
- targeted friendly effect: `946100-946199`
- targeted enemy instant/effect: `946200-946299`
- AOE centered on target: `946300-946399`
- ground-target AOE: `946400-946499`
- AOE centered on caster: `946500-946599`
- self aura, stance, or toggle: `946600-946699`
- random eligible targets: `946700-946799`
- passive aura: `946800-946899`
- frontal cone: `946900-946999`

Stock spells are seed/template/visual IDs only. They are not permanent WM carriers.

### Client And Server Truth

For a player-facing spellbook/action-bar ability:

1. claim the shell in `data/specs/custom_id_registry.json`
2. add/update the shell-bank contract
3. build and install client `patch-z.mpq`
4. stage the matching server `Spell.dbc` row
5. bind native behavior through `wm_spell_behavior`
6. grant through explicit character state and `wm_spell_grant`
7. restart/reload the right surfaces
8. prove the actual in-game button, tooltip, targeting, feedback, cooldown, resource cost, and revoke path

If the client shows the wrong requirement, buff, icon, text, or target shape, fix the shell or retire it. Do not hide the mismatch in native code.

### Active Abilities

If the user asks for an active button, make an active button.

Working strategy from `Skirmisher's Mark`:

- use a targeted active shell, not a passive and not a self-buff toggle
- the button casts on a hostile target
- native runtime performs one bounded action
- stock Auto Shot and Throw stay untouched
- readiness uses the equipped ranged/thrown weapon speed
- damage uses the core ranged auto-attack damage path
- feedback uses the equipped weapon shape: thrown weapon, bow, gun, or crossbow
- retired bad shells stay retired:
  - `946801`: passive moving pulse, `BROKEN`
  - `946604`: self-aura toggle, `BROKEN`

The durable lesson is stronger than the specific ability: do not model a direct attack as a buff because the buff is easier to implement.

### Passive Abilities

Passives can own hidden native behavior only when the player has a visible shell, correct tooltip, and scoped grant.

Working strategy from `Impossible Guard`:

- passive shell `946800`
- behavior gated by active `wm_spell_grant`
- no inherited stock shield requirement
- no inherited stock block chance effect
- tooltip states the real custom chance formula
- native code rolls custom mitigation against melee, direct spells, and periodic hostile effects
- melee success forces a core parry outcome when possible so the client can show `Parry`
- counter state is persisted through `wm_broug_guard_counter`

If a passive tooltip inherits a stock requirement like `Requires Shield`, the shell row is wrong. Clear the seed effect/requirement fields instead of explaining around it.

### Dispatch-Only Active Windows

Use dispatch-only rows for active buttons whose real behavior is native and should not leave a buff.

Working strategy from `Deflect`:

- active shell `946603`
- no aura, no duration, no effect payload in DBC
- native opens the guard window
- native handles resource cost, cooldown, root, block, feedback, and counter state
- visible results use separate status shells

This prevents the client from showing a fake buff when the ability is really an animation-timed server window.

### Visible Status Plus Native Authority

Use separate visible state shells for statuses the player or target should see.

Working strategy:

- `946200` / `Vulnerable`: visible stackable debuff
- `946201` / `Deflected`: visible stackable stun/status
- both use `StackAmount=255` so stack numbers can render
- native runtime owns actual damage amplification, stun, and release behavior
- aura presence is the control contract for `Deflected`

The key correction was to avoid a separate wall-clock stun authority. If `Deflected` is present, native enforces stun. If the aura is gone, native releases the stun and restarts creature combat.

### Stances

Use a real aura when gameplay state must be visible and player-toggleable.

Working strategy from `Counterstrike Stance`:

- shell `946605`
- real `SPELL_AURA_MOD_SHAPESHIFT`
- permanent duration index
- stance category and stance bar order set in client/server DBC
- native gates Deflect's automatic counterattack on `player->HasAura(946605)`
- recast removes the live aura

Do not use a DB-backed pseudo-toggle when the player expects a visible stance or aura state.

## Combat Proficiency Strategy

DBC validity prevents AzerothCore from deleting explicit character rows. It does not grant the skill by itself.

Working strategy:

- add server `skillraceclassinfo_dbc` rows so the skill is valid for the target race/class
- add server `skilllineability_dbc` rows with `AcquireMethod=2` when the skill should auto-learn a stock passive after the skill is obtained
- include matching client `SkillRaceClassInfo.dbc` and `SkillLineAbility.dbc` rows in the patch, or the skill frame can still hide the skill
- explicitly grant the character through the scoped proficiency CLI
- write `character_skills` and matching `character_spell` rows only for the target GUID
- keep an active `combat_proficiency` grant in `wm_spell_grant`
- let native materialize missing in-memory state only for active explicit grants and allowlisted players

Do not use:

- `playercreateinfo_skills`
- `playercreateinfo_spell_custom`
- `mod_learnspells`
- playerbot factory or maintenance paths
- broad login/update `SetSkill` hooks
- class/equip override hooks

Level gates belong in both DBC validity and the grant command. Plate for Broug remains locked until level `40`.

## Item Power Strategy

Managed item powers should be visible and reversible.

Working strategy:

- clone a known-good base item row
- claim the visible item ID before use
- put the player-facing description on the item
- use visible wearer or target state for hidden effects
- gate native hooks on that visible state
- publish through the managed item pipeline
- snapshot before apply
- support rollback and optional player-copy cleanup
- use a fresh quest ID if a visible quest reward changes

Do not solve hidden combat behavior with an item template alone when the behavior needs native hooks.

## Creature, Scene, Gameobject, And Weather Strategy

Temporary scenes should use typed native actions and WM-owned world-object records.

Working creature-scene strategy:

- spawn a WM-owned temporary creature
- record ownership in `wm_bridge_world_object`
- use typed follow-up actions by object id or arc key
- include duration or explicit cleanup
- refuse arbitrary nearby creature mutation

Current release-ready scene verbs include player aura/cast/display, item add/remove/random enchant, quest add/remove, creature spawn/despawn/say/emote/cast/display/scale, announcement, context snapshot, and debug actions.

Gameobject and real weather release lanes are not working yet. Until their native executors are implemented and proven, use creature deployables, local visual spells, auras, announcements, and scene actors.

## Proof And Documentation

End every feature with a hard status:

- `WORKING`: live player-facing proof passed for the stated scope
- `PARTIAL`: repo/build/DB proof passed, but live proof is missing or incomplete
- `BROKEN`: the visible ID or approach failed and must not be reused
- `UNKNOWN`: the state has not been checked

When a live proof passes:

1. update the feature-specific doc
2. update the current handoff if future sessions need it
3. update the custom ID ledger if status changed
4. record retired IDs and replacements
5. stop feature churn and move the lesson into this strategy reference when it generalizes

When a live proof fails three times:

1. stop tuning parameters
2. write the shared structural cause
3. retire failed visible IDs
4. continue only after the cause is known
