Status: DESIGN_ONLY
Last verified: 2026-04-30
Verified by: Codex
Doc type: design

# WM Roadmap

This is the canonical intended product direction for WM.

Current truth still lives in:

- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)
- [Work Summary](WORK_SUMMARY.md)
- [Summon and Spell Platform Status](SUMMON_SPELL_PLATFORM_STATUS.md)
- [Next Chat Handoff](NEXT_CHAT_HANDOFF.md)

## Product North Star

WM is a per-character World Master progression engine for AzerothCore 3.3.5a.

The product is not a quest generator, a bounty bot, an addon layer, or a platform-hardening project for its own sake. The goal is that each character develops a separate authored-by-play journey with:

- per-character arcs that respond to actual play history
- exclusive rewards, unlocks, proficiencies, companions, and power mutations
- managed quests, items, shell spells, deployables, and live scenes as reward surfaces
- item-granted alternate abilities, proc/rune/enchant systems, and companion synergies
- conversation steering that lets the player influence direction without giving the model mutation power

Architecture remains strict:

- Python owns decisions, state, validation, audit, publishing, rollback, arc logic, and director logic.
- Native modules own sensing, typed atomic actions, and shell-bound runtime behavior.
- `control/` is the shared manual and future LLM contract lane.
- The LLM may propose only structured plans from context packs and candidate packs; deterministic code validates, compiles, applies, and audits.
- No addon/log transport, combat-log scraping, freeform SQL lane, freeform GM-command lane, direct LLM mutation, or stock spell ID carrier roadmap.
- AzerothCore schema names such as `quest_template_addon` are database truth, not addon-layer architecture.

## Wild Feature Model

Every ambitious feature must be designed in this shape:

`trigger -> Python decision/state -> typed native actions or shell behavior -> client requirement tier`

Feature feasibility tiers:

- `T1`: server-only, but visible through existing game state such as messages, auras, items, quests, creature behavior, or inventory changes.
- `T2`: server plus existing client assets: stock visuals, icons, creature models, item displays, and known spell auras.
- `T3`: client patch required: spellbook/action-bar shells, owned tooltip presentation, stable custom DBC presentation.
- `T4`: client asset or UI work: new models, art, interface panels, frames, or non-DBC client behavior.
- `NOT FEASIBLE`: not reliable on stock 3.3.5a with WM's allowed contracts.

Wild features are product features only when the player can perceive them. Hidden server mechanics need a matching visible aura, buff, debuff, message, tooltip, item, creature, or scene state, and the hidden behavior must be gated by that visible state/duration.

Reusable archetypes:

- Night Watcher's Lens: managed item -> visible wearer aura -> visible target debuff -> native proc/runtime behavior -> fresh quest reward promotion.
- Bonebound Alpha: visible shell spell -> native summon/runtime behavior -> companion/Echo rules -> visible melee bleed with WM-owned ticks.
- Random Enchanting Vellums: scoped kill trigger -> Python drop decision -> native item grant -> player menu choice -> bounded item mutation.
- Bone Lure: consumable item -> ground-target UX -> WM-owned temporary creature -> typed taunt/threat behavior -> explicit expiry/release rules.
- Area-pressure scene: event pattern -> Python opportunity decision -> typed native announcement/aura/restore/spawn actions -> audited scene result.

## Wild Feature Lanes

These lanes are the product center. Platform work is valuable when it unlocks one of them.

- Per-character arcs: multi-step personal stories with state, beats, choices, unlocks, reward instances, and replayable audit.
- Exclusive rewards: items, abilities, proficiencies, companions, scenes, and mutation rights granted to one character through explicit records.
- Item-granted powers: equipped or consumed items that alter shell behavior, proc behavior, combat hooks, or companion behavior while visibly active.
- Shell-bank powers: spellbook/action-bar abilities using WM-owned shell identities, not stock spell carriers.
- Companion behavior: Alpha/Echo/Restorer-style owned actors with visible roles, commands, scaling, reacquire rules, and owner-scoped state.
- Deployables and live scenes: Bone Lure-style objects, temporary actors, area pressure, warnings, rescues, ambushes, rituals, and cleanup.
- Random enchant/rune systems: kill- or arc-triggered consumables that apply bounded, auditable item mutations with player choice where needed.
- Conversation steering: durable preferences and branch prompts that shape future proposals without mutating game state directly.

## Track 1: Personal Journey Spine

Goal: make each character's WM state first-class.

Build:

- per-character profile, arc state, journal state, unlock state, reward-instance state, prompt queue, and recent decision history
- context packs that combine character state, target subjects, zone history, active quests, companions, and eligible wild feature candidates
- conversation steering records that turn player/operator intent into bounded arc preferences
- inspect tools that explain eligibility and blockers for arcs, powers, rewards, companions, and scenes
- player isolation so broadcasts, bot state, rewards, and unlocks never leak from the active WM character to others

Exit criteria:

- one command explains a character's active arcs, completed beats, unlocks, reward instances, and steering notes
- a new feature can ask "is this character eligible?" without scraping logs or reinterpreting arbitrary quest state
- stale lab rows and other players' events cannot influence active-character decisions

## Track 2: Arc + Reward Factory

Goal: turn play events and context packs into multi-step character arcs with managed rewards.

Build:

- two-to-three beat arc drafts with objectives, turn-in choices, branch outcomes, and rollback metadata
- managed quest publishing through fresh reserved slots, never mutating visible rewards on already accepted/rewarded quest IDs
- managed item rewards with snapshots, publish logs, rollback, direct grants, and optional cleanup primitives
- shell-backed spell rewards and visible ability unlocks through the shell bank
- reward promotion flows that turn proven items/powers into fresh quest rewards without bypassing slot governance
- arc outcome records feeding the Personal Journey Spine

Current V1 slice:

- repo `WORKING` / BridgeLab DB `WORKING` / gameplay `PARTIAL`: `control/examples/arcs/jecia_shadowmoon_lens_arc_v9.json` validates a three-beat Jecia arc fitted to her level-70 Shadowmoon context, while the live proof quest is cloned directly from known-working quest `910151`
- BridgeLab source quest is `910171`; v9 uses fresh reward item `910013` cloned from the proven Lens row and clones the proven visible-reward quest row `910151`, changing identity, current-zone objective, Earthmender Wilda starter/ender, all visible quest text fields, and reward item while clearing visible money. `control/examples/content_playcycles/shadowmoon_watchers_lens_arc_reward.json` verifies the `910013` item-effect lane with direct grant disabled so the quest remains the acquisition path. The older Elwynn proof quest `910151` is retained as a regression artifact, not the live target. Bad Shadowmoon IDs `910152` / `910010`, `910154` / `910011`, `910155` / `919001`, `910160` / `919002`, `910167` / `919003`, `910168` / `919004`, `910169` / `919005`, and `910170` / `910012` are retired and must not be reused.

Exit criteria:

- WM can create and publish one per-character arc from a context pack
- that arc rewards a managed item or shell-backed ability through fresh slots
- rollback reports DB state, player-copy cleanup limits, grant history, and remaining manual cleanup clearly
- reward visibility is proven in BridgeLab before the feature is marked `WORKING`

## Track 3: Wild Powers

Goal: make character-exclusive power growth the main excitement lane.

Build:

- character-exclusive ability unlocks with persistent grant records and clear revoke paths
- item-granted alternate abilities, such as weapons or trinkets changing how a known shell behaves while equipped
- shell-bank spell rewards with spellbook/action-bar presentation when the player needs a button
- combat proficiencies, passive stat conversions, and companion synergies tied to explicit grants
- proc, rune, enchant, and vellum systems where Python decides eligibility/drop and native code performs bounded item/runtime mutation
- companion power upgrades for Alpha/Echo/Restorer behaviors that stay owner-scoped and visible

Exit criteria:

- at least one arc grants a character-exclusive power that is visible, persistent, auditable, and reversible
- each item/shell power has a documented feasibility tier and client-truth requirement before implementation
- random/proc systems are scoped to the active WM player and cannot mutate arbitrary inventory globally

## Track 4: Live Scene Director

Goal: let WM stage small live encounters and interventions around one character.

Build:

- WM-owned temporary actors, objects, deployables, and scene records
- typed scene actions for spawn, despawn, say, emote, cast, aura, restore, display/scale, and future safe movement/gossip hooks
- area-pressure reactions that use the event spine without a second watcher engine
- deployable mechanics such as Bone Lure that are consumable, visible, scoped, and explicit about release/leash behavior
- companion interventions that assist, warn, taunt, mark, protect, punish, or alter combat through typed native actions
- gossip/menu hooks only through registered contracts, never arbitrary command strings

Exit criteria:

- a scene can be replayed from audit: source event -> proposal -> native requests -> result -> cleanup
- every spawned or mutated world object is WM-owned or explicitly rejected
- boss/no-taunt/no-owner rules are encoded in native behavior, not left to operator memory

## Track 5: LLM On Locked Contracts

Goal: use local model creativity without exposing mutation authority.

Build:

- context packs containing character state, subject cards, recent events, active arcs, companions, eligible recipes, and policy gates
- candidate packs for arcs, rewards, powers, and scenes that the model can select from or fill within strict schemas
- proposal schemas for arc plans, reward plans, scene plans, power plans, and conversation steering
- deterministic compilers that turn accepted proposals into control proposals, managed publishes, or native action sequences
- direct apply disabled by default and always gated by policy, player scope, idempotency, stale-event checks, and audit

Exit criteria:

- LLM output can be rejected without side effects
- no proposal schema includes arbitrary SQL, GM commands, shell commands, config edits, file mutation, or stock spell carrier reuse
- manual operator proposals and LLM proposals use the same validators and apply paths

## Platform Gates For Wild Features

These are gates, not the product:

- native bounty full loop: trigger -> grant -> complete -> reward -> suppress -> cooldown -> regrant
- BridgeLab health: one-shot launcher, stable MySQL on `127.0.0.1:33307`, scoped player `5406`, clean watcher start, and clear restart/reload rules
- native action audit: every typed action has policy defaults, payload validation, scoped execution, result JSON, and lab proof
- Echo proof: Echoes keep attacking instead of following and staring; seek/follow/teleport/restorer behavior is proven in-game
- context packs: deterministic nearby/player/subject snapshots consumed by arc, power, and scene candidates
- rollback and cleanup: managed quests/items/spells report DB rollback, grant state, player-copy limits, and cleanup status
- shell-bank client truth: client MPQ and server DBC are treated as separate gates before spellbook/action-bar claims
- content release pipeline: quests, abilities, items, spawns, events, and environment effects are released from fixed schemas with fresh IDs, dry-run/apply separation, runtime-sync proof, and explicit status labels
- player isolation: active WM player scope remains the default for broadcasts, drops, rewards, and scene effects

Current V1 pipeline slice:

- repo `WORKING` / gameplay `PARTIAL`: `wm.content.release` validates repeatable bounty, one-shot quest, story arc, shell ability, managed item power, and native scene sequence specs from `control/examples/content_releases/`.
- release specs can render a gate/command plan with `--plan`, emit validation/plan/artifact/proof packets with `--packet`, write guarded packet files with `--write-packet-dir`, and templates can be batch-audited with `--audit-dir`; scene specs can emit strict `control.scene.v1` JSON for the existing scene-play workflow while rejecting unimplemented `gameobject_*` and real weather actions until native executors exist.
- story arc specs can emit strict journey plans plus non-mutating branch-lock contracts for first-completed-choice behavior, and the CLI can report ability shell coverage plus scene action readiness through `--ability-roster` and `--scene-action-roster`.
- context packs can now produce deterministic `wm.release_candidate_pack.v1` candidate packs, ready `*.release.json` files, optional per-candidate release packet directories, and consolidated release-test manifests for repeatable bounty, story arc, shell ability, and native scene lanes before any LLM proposal mode is introduced; managed item-power candidates remain blocked by default and become ready only when a fresh item entry plus base item entry are explicitly supplied.

## Medium-Term Execution Order

1. Finish native bounty full-loop proof on a clean BridgeLab window: grant, complete, reward, suppress, cooldown, and regrant.
2. Prove current Bonebound Echo seek/reacquire/restorer behavior in-game and update status labels.
3. Use the live-proven Personal Journey Spine V1 and `JourneyEligibilitySnapshot` as the eligibility source for arcs, rewards, powers, and scenes.
4. Finish Arc + Reward Factory V1 gameplay proof: have Jecia accept/complete Shadowmoon quest `910171` and confirm reward visibility for item `910013`.
5. Build Wild Power Pack V1: one item-granted alternate ability, one shell/proficiency unlock, and one bounded rune/enchant extension.
6. Build Companion Pack V1: Alpha/Echo command polish, visible counters/status, role-specific Echo upgrades, and owner-scoped progression hooks.
7. Build Live Scene Pack V1: one area-pressure scene and one WM-owned actor/deployable scene with full audit and cleanup.
8. Add LLM proposal mode only after manual schemas and deterministic compilers are stable enough to be boring.

## Not Roadmap

These are intentionally outside the direction:

- addon/log transport as a future architecture lane
- combat-log scraping as a product perception path
- Eluna or another parallel runtime as the main WM brain
- freeform SQL, GM commands, shell commands, config edits, or file mutations from LLM proposals
- stock spell IDs as permanent WM carriers
- global broadcasts, drops, rewards, or bot-state changes while testing one WM character
- quest-only spam that does not feed character arcs, exclusive rewards, powers, companions, or scenes
- broad coordinator splitting before behavior is locked by tests and live proof
- hidden stat/combat effects without player-visible state

The platform exists to ship personal journeys, wild rewards, companion growth, and live interventions. If a task does not unlock those product outcomes, treat it as a gate or maintenance item, not the roadmap center.
