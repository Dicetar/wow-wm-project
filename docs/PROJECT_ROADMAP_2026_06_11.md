# WM Project Roadmap - 2026-06-11

Status: CURRENT_ROADMAP
Last verified: 2026-06-12
Scope: project-wide direction after reviewing repository docs, historical notes, transcripts, current code layout, validation commands, and the live runtime status.

This roadmap is an analysis artifact. It does not replace the existing handoff and runbook docs for exact operating steps. For current operational truth, prefer:

- `docs/NEXT_SESSION_HANDOFF_2026_06_08.md`
- `docs/WM_PLATFORM_HANDOFF.md`
- `docs/FULL_LOOP_PROOF_RUNBOOK.md`
- `docs/LIVE_PROOF_BACKLOG.md`
- `data/specs/feature_status.json`

## 1. Product North Star

WM is a local, external-first World Master for AzerothCore/WoW 3.3.5a. It should feel like a bounded GM/director living around one character, not like a generic chatbot, quest generator, or admin panel.

The desired product shape is:

- observe real play through native and database truth;
- remember meaningful character-specific facts;
- speak and react in-game through typed, audited actions;
- stage small temporary scenes;
- generate and publish managed quests, items, spells, rewards, and world flavor through gates;
- grant exclusive per-character progression, companions, proficiencies, powers, mutations, and narrative consequences;
- prove every live claim with runtime, database, native result, or client-visible evidence;
- keep the LLM advisory and schema-bound, never directly mutating the world.

The strongest recurring user intent across historical docs and transcripts is practical live usability. The project should keep favoring small, repeatable, end-to-end loops over theoretical capability expansion.

## 2. Architecture Principles

The project direction is consistent across the newest docs:

- Python owns planning, validation, publishing, rollback, audits, memory, subject resolution, release packets, director logic, and policy.
- Native modules own in-process sensing, typed atomic actions, shell spell behavior, safety checks, and passive runtime bookkeeping.
- MySQL and client files are real truth surfaces. Server DB state, client DBC/MPQ state, and native runtime state must not be treated as interchangeable.
- The control plane is contract-first. New live mutations should flow through typed action kinds, release packets, or shell spell behavior, not raw SQL, GM commands, ad hoc shell calls, or direct LLM mutation.
- The addon/combat-log path is fallback or compatibility only. The current product direction is native-first truth.
- New gameplay claims need evidence labels: repo-tested, BridgeLab-tested, live in-client proven, partial, or broken.

Non-negotiable constraints from the docs:

- never reuse stock live spell IDs as WM carriers;
- never hide client/server mismatch behind server-only success;
- do not build a second native action runner beside the existing WM action bus;
- stop after repeated failed attempts and write down the failure mode;
- clean lab state before summon, pet, shell, bounty, and character-bound tests;
- keep LLM output constrained to schemas, drafts, and reviewed plans.

## 3. Current Verified State

The active project center is `wm-project`. The wider workspace also contains historical docs, exported data, repack/client folders, and `WM_BridgeLab`, but current development truth lives in `wm-project`.

Validation performed on 2026-06-11:

- `python -m wm.status --validate`: OK.
- `python scripts\validate_agent_skills.py`: OK.
- `python -m pytest -q`: 1194 passed, with warnings only.
- `python -m wm.doctor --profile bridgelab --summary`: all 8 checks working.
- `python -m wm.panel summary --json`: panel/status sources working; living catalog reports 5/5 live-ready; native contracts report 63/100 action kinds contracted.
- `python -m wm.runtime status --json`: runtime status OK, with incidents for limited Windows process scanning and stale Native Watcher marker heartbeat.
- `python -m wm.autoplay status --summary`: autoplay running with LLM enabled and in-game chat lane active.
- `python -m wm.living.catalog --validate --json`: OK.
- `python -m wm.sources.native_bridge.contracts_cli --json`: 100 total native action kinds, 63 contracted, 37 uncontracted.

Continuation verification on 2026-06-12:

- Stale Native Watcher markers were cleared and the watcher was restarted for player GUID 5408.
- `python -m wm.runtime status --json`: DB/Auth/World/Watcher/Panel/Autoplay all report running.
- `python -m wm.proofs run runtime_startup --project-root D:\WOW\wm-project --mode record --json`: service checks pass in proof `proof-20260612113900858342`; packet status remains `manual_required` because operator-visible live confirmation is still required.
- `python -m wm.autoplay status --summary`: autoplay is running and now reports `client_running=false scoped_player_online=false`.
- `acore_characters.characters` reports GUID 5408 (`Astel`) as `online=0`, so `chat_action` cannot pass until the WoW client logs in that character.
- `python -m pytest -q`: 1197 passed.

Current marker-targeting update on 2026-06-24:

- The active gameplay target is no longer a named fixture character. Operational
  proof work must resolve whichever online character most recently receives
  canonical marker aura `946602` (`WM Watcher Beacon`).
- Current marker scan is blocked: `python -m wm.sources.native_bridge.player_marker scan --spell-id 946602 --since-seconds 86400 --limit 20 --db-profile bridgelab --summary`
  reports `count=0`.
- BridgeLab doctor is otherwise healthy: `python -m wm.doctor --profile bridgelab --summary`
  reports 8/8 checks working, with temporary wildcard observation still active
  for marker discovery.
- Current repo gate: `python -m pytest -q` reports `1244 passed, 31 warnings`;
  status, skills, native contracts, living catalog, and diff validation pass.
- The worktree is clean. Continue by reapplying aura `946602` to the intended
  online client character, then run marker scan and `scope-latest`.

Important current caveat: gameplay status must not be promoted from tests alone. Live phases remain blocked until a fresh online marker-selected target exists.

## 4. Main Gap

The repo foundation is now much stronger than the live proof foundation.

Tests, docs, panel summaries, schemas, contracts, and doctor checks are healthy enough to support the next step. The remaining critical gap is repeatable in-game proof that a launcher-started WM session can:

1. start cleanly;
2. observe the intended player/session;
3. accept in-game WM chat;
4. respond in-game;
5. apply bounded typed actions after gates;
6. reuse durable memory;
7. stage and clean up a small scene;
8. show proof packets/timeline entries that survive review.

Until that loop is boring and repeatable, broad feature expansion should stay secondary.

## 5. Roadmap

### Phase 0 - Stabilize The Current Tree

Goal: turn the current large dirty implementation into a known baseline.

Tasks:

- Split or commit the current native, Python, docs, SQL, addon, and test changes intentionally.
- Update `data/specs/feature_status.json` so machine-readable status matches the current code and proof state.
- Re-run the full validation set after the dirty tree is stabilized.
- Build the native BridgeLab modules after the new C++ action files and SQL updates are included.
- Decide which newly implemented action kinds are product verbs, debug verbs, or internal-only helpers.
- Keep debug/context exceptions explicit in the contract report instead of letting them look like missing product work.

Done when:

- the worktree can be explained file-by-file;
- tests and doctor remain green;
- native build status is known;
- feature status and docs no longer disagree about the same capability.

### Phase 1 - Repeatable Live-Proof WM Session

Goal: prove the product's basic promise in a local live session launched through the normal WM path.

Priority proof kinds:

- `runtime_startup`
- `chat_action`
- `ambient`
- `memory`
- `scene`
- `failure`

Tasks:

- Repair or refresh the stale Native Watcher heartbeat marker.
- Make launcher startup produce a clean proof packet for DB/Auth/World/Panel/Watcher/Autoplay.
- Prove player chat through the WM channel or `/wm` path produces an in-game WM response.
- Prove at least one low-risk typed action from chat intent to native result to client-visible effect.
- Prove one ambient reaction with cooldown/suppression.
- Prove one memory write and later reuse in a separate prompt or reaction.
- Prove one small scene that spawns, acts, and cleans up.
- Surface all proof records in the panel checklist/timeline.

Done when:

- the same local player can repeat the loop after restart;
- proof evidence is tied to the latest runtime start, not stale rows;
- failures are recorded as first-class proof records rather than hidden logs.

### Phase 2 - Runtime And Proof Reliability

Goal: make runtime state and proof evidence trustworthy enough for daily development.

Tasks:

- Treat limited Windows process scan access as an expected degraded mode with clear status wording.
- Make stale runtime markers actionable in panel and CLI output.
- Add a small replay/evaluation harness for proof packets.
- Create a "current live session" view that distinguishes running services, stale markers, latest native action result, latest chat event, and latest proof event.
- Add regression checks for proof freshness after service restart.

Done when:

- a developer can tell in under one minute whether the live stack is currently trustworthy;
- stale or pre-restart evidence cannot accidentally satisfy a proof gate.

### Phase 3 - Conversational Action Loop Productization

Goal: connect in-game conversation to bounded gameplay action without giving the LLM raw power.

Tasks:

- Keep chat parsing and LLM intent drafting schema-bound.
- Route accepted intents through dry-run, policy, contract validation, execution, native result, and audit.
- Add clear player-facing failure responses for blocked, invalid, cooldowned, or unsafe actions.
- Start with low-risk verbs: player message, sound, emote, companion say/follow/wait, small creature say/emote, small temporary spawn/despawn.
- Only graduate verbs after live proof and rollback/cleanup behavior are known.

Done when:

- chat can trigger a small set of reliable actions;
- every accepted action has a matching audit trail;
- every rejected action explains itself without exposing implementation noise.

### Phase 4 - Native Action Surface Consolidation

Goal: turn the expanded native verb set into a contracted, tested, product-ready surface.

Tasks:

- Contract every implemented non-debug action kind.
- Keep implemented debug verbs separated from player/product verbs.
- Live-proof the highest-value verbs before adding more:
  - player chat/message/sound;
  - creature spawn/despawn/say/emote/move/follow;
  - gameobject spawn/despawn/state;
  - companion spawn/follow/wait/say/emote;
  - quest add/complete/fail/counters;
  - item add/remove/mail/enchant;
  - aura/cast/learn/unlearn for managed shells only.
- Add action-specific cleanup recipes for temporary world objects.
- Keep DB action bus semantics stable.

Done when:

- contract coverage represents the actual implemented surface;
- new verbs have tests, CLI examples, and proof runbook entries;
- no feature depends on undocumented native behavior.

### Phase 5 - Memory, Subject, And Context

Goal: make WM remember and reason over the right things without drifting from game truth.

Tasks:

- Move journal V2 and projector work from partial proof to live-session proof.
- Feed deterministic context packs into chat, ambient reactions, and content proposals.
- Improve subject recognition from native events and DB facts.
- Auto-materialize or repair subject records only through typed, audited paths.
- Add player-visible memory controls in the panel: inspect, pin, suppress, forget, and explain source.
- Keep generated prose separate from factual state.

Done when:

- WM can refer to a recent event correctly in a later session;
- memory use is visible and correctable;
- subject identity is grounded in DB/runtime evidence.

### Phase 6 - Managed Content And Artifact Proof

Goal: make quests, items, spells, rewards, and rollback safe enough for regular use.

Tasks:

- Complete the ADR-0004 proof: compiler output, not hand-cloned SQL, is accepted, completed, and shows the correct reward panel in-client.
- Finish the full native reactive bounty proof: trigger, grant, complete, reward, suppress, cooldown, regrant.
- Make quest rollback uniform and gate-aware.
- Keep item and spell publication behind release packets, ID registry checks, DBC/client patch checks, and restart requirements.
- Expand proposal producers for quest, item, spell, scene, and action lanes only after Phase 1 proof is repeatable.
- Preserve shell-bank discipline for client-visible abilities.

Done when:

- at least one compiler-generated quest artifact completes in the client with correct visible rewards;
- rollback and suppression are demonstrated;
- release packets carry enough provenance to audit or undo the change.

### Phase 7 - Living World Lanes

Goal: graduate living systems from catalog readiness to gameplay reality.

Priority order:

1. Rumor: low-risk world flavor and information propagation.
2. Patron/Oath: character-specific commitments and consequences.
3. Nemesis: recurring opponent state with cooldowns and escalation.
4. Legend: long-term reputation and story accumulation.
5. Scene director: multi-actor temporary situations with cleanup.

Tasks:

- Prove each lane with one narrow, repeatable in-game loop.
- Keep lane state in WM-owned tables and audits.
- Add cooldowns, suppression, and rollback/cleanup from the start.
- Avoid turning every lane into a content generator before the live reaction loop is stable.

Done when:

- each lane has at least one live proof, one failure proof, and one cleanup/suppression proof;
- panel status distinguishes catalog readiness from gameplay proof.

### Phase 8 - Operator UX And Release Hygiene

Goal: make the system easy to run, inspect, and recover.

Tasks:

- Keep one canonical launcher path for local play.
- Make panel proof checklists, timelines, LLM drafts, native actions, service state, and rollback controls coherent.
- Archive or clearly mark stale docs so old prototype instructions do not mislead future work.
- Add a doc index that points to current truth, historical context, and retired experiments.
- Keep CI focused on contracts, catalog validation, proof schema validation, status validation, and unit tests.
- Package a local "v1 playable lab" profile with exact prerequisites and expected proof output.

Done when:

- a future session can start from docs and reproduce the main live loop without rediscovering hidden state;
- stale prototype docs are useful history, not operational instructions.

### Later - Advanced WM Powers

Only after the live proof loop is reliable:

- companion behavior packs;
- shell ability families;
- rune/enchant/proc systems;
- personal proficiency trees;
- temporary domain or aura scenes;
- richer player choice/consequence arcs;
- generated dungeon/event agendas;
- stronger LLM-assisted content authoring.

These should be built as sequences of existing typed actions, shell behaviors, release packets, and memory updates. The old "wild feature" docs are useful idea catalogs, not permission to bypass the current architecture.

## 6. Immediate Next Work

Recommended next seven development tasks:

1. Stabilize the current dirty tree and update machine-readable status.
2. Repair or refresh the stale Native Watcher runtime marker.
3. Run a clean launcher-started runtime proof and record `runtime_startup`.
4. Prove in-game WM chat response through the active chat lane.
5. Prove one low-risk chat-triggered native action with visible client evidence.
6. Prove one memory write/reuse and one small scene cleanup.
7. Update the handoff with exact proof IDs, timestamps, blockers, and status labels.

Do not start a broad new feature lane before these are done.

## 7. Risk Register

Status inflation:
Repo tests and dry-runs can make a feature look done before it is client-visible. Keep status labels strict.

Client/server mismatch:
Spells, icons, names, rewards, and visible abilities need client truth as well as server truth.

Prototype poisoning:
Old stock spell carrier and summon experiments are documented failures. Keep them retired.

Native scope creep:
The native layer should stay typed and boring. Add verbs because a proof loop needs them, not because they are interesting.

LLM overreach:
The LLM should draft, summarize, select, and propose. It should not write freeform SQL, run GM commands, mutate config, or bypass gates.

Dirty lab state:
Old rows, stale sessions, cached client files, existing pets, and old proof events can create false positives.

Docs drift:
There are many historical docs. Current-state docs need status headers and old docs need clear archival framing.

## 8. Definition Of Done For Future Features

A feature is not done because code exists.

Use these labels:

- BROKEN: known to fail or unsafe.
- DESIGN: architecture or plan only.
- REPO_WORKING: unit tests, schemas, or dry-runs pass.
- BRIDGELAB_WORKING: works against the local BridgeLab DB/runtime profile.
- LIVE_PARTIAL: some in-client behavior proven, with known gaps.
- LIVE_WORKING: repeated current-session in-client proof with audit/proof records.
- RELEASE_READY: documented, reproducible, rollback-aware, and included in operator docs.

For gameplay-facing features, the target is LIVE_WORKING before calling the feature complete.
