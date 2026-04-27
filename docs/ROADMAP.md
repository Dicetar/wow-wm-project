Status: DESIGN_ONLY
Last verified: 2026-04-26
Verified by: Codex
Doc type: design

# WM Roadmap

This is the canonical intended direction for WM.

Current truth still lives in:

- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)
- [Work Summary](WORK_SUMMARY.md)
- [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)

## Product North Star

WM is a per-character World Master progression engine for AzerothCore, not a quest-generator checklist and not a platform-hardening project for its own sake.

The product goal is that each character can develop a separate authored-by-play journey:

- character-specific arcs that respond to the player's actual history
- exclusive rewards, unlocks, proficiencies, companion behaviors, and power mutations
- managed quests, items, and visible shell-backed abilities as reward surfaces
- item-granted alternate abilities and proc/rune/enchant systems
- live scenes, temporary actors, area pressure, deployables, and companion interventions
- conversation steering that lets the player influence arc direction without giving the model mutation powers

Architecture remains strict:

- Python owns decisions, state, validation, audit, publishing, rollback, arc logic, and director logic.
- Native modules own sensing, typed atomic actions, and shell-bound runtime behavior.
- `control/` is the shared manual and future LLM contract lane.
- The LLM may propose only structured plans from candidates and context packs; deterministic code validates, compiles, applies, and audits.
- No addon/log transport, combat-log scraping, freeform SQL lane, freeform GM-command lane, direct LLM mutation, or stock spell ID carrier roadmap.
- AzerothCore schema names such as `quest_template_addon` are database truth, not addon-layer architecture.

## Wild Feature Model

Every ambitious feature must be described in the same contract shape:

`trigger -> Python decision/state -> typed native actions or shell behavior -> client requirement tier`

Feature feasibility tiers:

- `T1`: server-only; visible through existing server events, messages, auras, items, quests, or creature behavior.
- `T2`: server plus existing client assets; no new client patch, but uses known spell visuals, icons, item displays, or creature models.
- `T3`: client patch required; new spellbook/action-bar shells, owned tooltip presentation, or stable custom DBC presentation.
- `T4`: client asset or UI work; new art, UI panels, frames, custom widgets, or non-DBC client behavior.
- `NOT FEASIBLE`: cannot be made reliable on stock 3.3.5a with WM's allowed contracts.

Wild features are product features only when the player can perceive them. Hidden server mechanics need a matching visible aura, buff, debuff, message, tooltip, item, creature, or scene state, and hidden behavior must be gated by that visible state/duration.

Reusable archetypes:

- Night Watcher's Lens: managed item -> visible wearer aura -> visible target debuff -> native proc/runtime behavior -> fresh quest reward promotion.
- Bonebound Alpha: visible shell spell -> native summon/runtime behavior -> companion/Echo rules -> visible melee bleed with WM-owned ticks.
- Random Enchanting Vellums: scoped kill trigger -> Python drop decision -> native item grant -> player menu choice -> bounded item mutation.
- Bone Lure: consumable item -> ground-target UX -> WM-owned temporary creature -> typed taunt/threat behavior -> explicit expiry/release rules.
- Area-pressure scene: event pattern -> Python opportunity decision -> typed native announcement/aura/restore/spawn actions -> audited scene result.

## Track 1: Personal Journey Spine

Goal: make each character's journey state first-class.

Build:

- per-character arc state, journal state, unlock state, reward-instance state, and recent decision history
- profile/context packs that combine character state, target subjects, zone history, active quests, companions, and eligible feature candidates
- conversation steering records that turn player intent into bounded arc preferences, not direct mutation
- inspect tools that explain why a character is eligible or blocked for an arc, reward, power, or scene
- player isolation so no WM unlock, broadcast, bot state, or reward leaks to another character

Exit criteria:

- an operator can inspect one character and see active arcs, completed beats, unlocked powers, granted reward instances, and conversation steering notes
- a new feature can ask "is this character eligible?" without re-reading arbitrary quest logs or scraping chat
- stale lab rows and other players' events cannot influence the active character's arc decisions

## Track 2: Arc + Reward Factory

Goal: turn play events into multi-step character arcs with managed rewards.

Build:

- multi-quest arc drafts with objective beats, turn-in choices, reward branches, and rollback metadata
- managed quest publishing through fresh reserved slots, never mutating visible rewards on already accepted/rewarded test IDs
- managed item rewards with snapshots, publish logs, rollback, direct grants, and optional cleanup primitives
- shell-backed spell rewards and visible ability unlocks that use the shell bank instead of stock carriers
- promotion flows that can turn a proven reward into a fresh quest reward without bypassing slot governance
- arc outcome records that feed the Personal Journey Spine

Exit criteria:

- WM can create a two-to-three beat per-character arc from a context pack and reward it with a managed item or shell-backed ability
- rollback reports DB state, player-copy cleanup limits, grant history, and remaining manual cleanup clearly
- reward visibility is proven in BridgeLab before any feature is marked `WORKING`

## Track 3: Wild Powers

Goal: make character-exclusive power growth the main excitement lane.

Build:

- character-exclusive ability unlocks with persistent grant records and clear revoke paths
- item-granted alternate abilities, such as a weapon changing how a known spell or shell behaves while equipped
- shell-bank spell rewards with visible spellbook/action-bar presentation when the feature requires a button
- combat proficiencies, passive stat conversions, and companion synergies tied to explicit grants
- proc, rune, enchant, and vellum systems where Python decides eligibility/drop and native code performs bounded item/runtime mutation
- companion powers such as Alpha/Echo behaviors that stay tied to the owning character and visible combat state

Exit criteria:

- at least one arc grants a character-exclusive power that is visible, persistent, auditable, and reversible
- item and shell powers have a documented feasibility tier and client-truth requirement before implementation
- random/proc systems are scoped to the active WM player and cannot mutate arbitrary inventory globally

## Track 4: Live Scene Director

Goal: let WM stage small live encounters and interventions around one character.

Build:

- WM-owned temporary actors, objects, deployables, and scene records
- typed scene actions for spawn, despawn, say, emote, cast, aura, restore, display/scale, and future safe movement/gossip hooks
- area-pressure reactions that use event spine opportunities without a second watcher engine
- deployable mechanics such as Bone Lure that are consumable, visible, scoped, and explicit about release/leash behavior
- companion interventions that can assist, warn, taunt, mark, or alter combat through native typed actions
- gossip/menu hooks only through registered contracts, never arbitrary command strings

Exit criteria:

- a scene can be replayed from audit: source event -> proposal -> native requests -> results -> cleanup
- every spawned or mutated world object is WM-owned or explicitly rejected
- boss/no-taunt/no-owner rules are encoded in native behavior, not left to operator memory

## Track 5: LLM On Locked Contracts

Goal: use local model creativity without exposing mutation authority.

Build:

- context packs containing character state, subject cards, recent events, active arcs, eligible recipes, and policy gates
- candidate packs for arcs, rewards, powers, and scenes that the model can select from or fill within strict schemas
- proposal schemas for arc plans, reward plans, scene plans, and conversation steering
- deterministic compilers that turn accepted proposals into control proposals, managed publishes, or native action sequences
- direct apply disabled by default and always gated by policy, player scope, idempotency, stale-event checks, and audit

Exit criteria:

- LLM output can be rejected without side effects
- no schema includes arbitrary SQL, GM commands, shell commands, config edits, file mutation, or stock spell carrier reuse
- manual operator proposals and LLM proposals use the same validators and apply paths

## Platform Gates For Wild Features

These are gates, not the product:

- native bounty full loop: trigger -> grant -> complete -> reward -> suppress -> cooldown -> regrant
- BridgeLab health: one-shot launcher, stable MySQL on `127.0.0.1:33307`, scoped player `5406`, clean watcher start, and clear restart/reload rules
- native action audit: every typed action has policy defaults, payload validation, scoped execution, result JSON, and lab proof
- Echo reacquire proof: build/deploy and in-game validation that Echoes keep attacking instead of following and staring
- context packs: deterministic nearby/player/subject snapshots consumed by arc and scene candidates
- rollback and cleanup: managed quests/items/spells can report DB rollback, grant state, player-copy limits, and cleanup status
- shell-bank client truth: client MPQ and server DBC are treated as separate gates before spellbook/action-bar claims

## Near-Term Execution Order

1. Prove the current native bounty full loop on a clean BridgeLab window.
2. Deploy and prove Bonebound Echo reacquire hardening, then update live status.
3. Implement Personal Journey Spine V1: character arc state, unlock records, reward-instance records, and inspect output.
4. Build Arc + Reward Factory V1: a two-to-three beat per-character arc that rewards a managed item or shell-backed ability through fresh slots.
5. Build Wild Power Pack V1: one item-granted alternate ability and one character-exclusive shell/proficiency unlock.
6. Build Live Scene Pack V1: one area-pressure scene plus one WM-owned actor/deployable scene with full audit and cleanup.
7. Add LLM proposal mode only after the manual schemas and deterministic compilers are boringly reliable.

## Not Roadmap

These are intentionally outside the direction:

- addon/log transport as a future architecture lane
- combat-log scraping as a product perception path
- Eluna or another parallel runtime as the main WM brain
- freeform SQL, GM commands, shell commands, config edits, or file mutations from LLM proposals
- stock spell IDs as permanent WM carriers
- global broadcasts or rewards that affect bots/other players while testing one WM character
- quest-only spam that does not feed character arcs, exclusive rewards, powers, or scenes
- broad coordinator splitting before behavior is locked by tests and live proof
- hidden stat/combat effects without player-visible state

The platform exists to ship personal journeys, wild rewards, and live interventions. If a task does not unlock those product outcomes, treat it as a gate or maintenance item, not the roadmap center.
