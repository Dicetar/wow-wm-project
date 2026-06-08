# WM Next Session Handoff - 2026-06-08

Status: active project handoff  
Repository: `D:\WOW\wm-project`  
Branch: `main`  
Latest implementation commit at handoff: `bce5fd7 Add live proof evidence checks`  
Previous key commit: `fd416ff Add runtime heartbeats and live proof checklist`  
Current priority: make one launcher-started local WM session repeatedly prove live in-game autonomy

## Executive Summary

World Master is a local autonomous WoW control plane. The intended product is not a chatbot beside the game. It is a bounded local World Master that observes the live game, speaks in-game, chooses safe actions, verifies outcomes, remembers durable facts, stages small scenes, proposes content through gates, and exposes all of this through one launcher and one panel.

The project has moved past platform skeleton. The current codebase has strong pieces for launcher/runtime truth, panel APIs, autoplay chat, intent handling, ambient narration, memory capture, scene composition, native bridge action contracts, content release gates, and observability. The main gap is live proof discipline: many lanes are implemented or test-proven in fake/integration contexts, but only a narrow set should be considered in-client proven. The next session should focus on the repeatable proof path, not broad feature expansion.

The current sprint theme is **Live-Proof WM Playability**:

1. Clean startup with exactly one logical runtime stack.
2. Player chat action for proof player.
3. One ambient reaction without spam.
4. One durable memory and later reuse.
5. One small scene with cleanup.
6. All visible in panel proof checklist/timeline.

## Product Vision

Target player experience:

- Start `WM Launcher`.
- Press `Start Core`, then start `Panel`, `Watcher`, and `Autoplay`.
- Enter WoW with the scoped character.
- Talk to WM in the in-game `WM` channel or supported fallback.
- WM replies in-game, not only in an external panel.
- WM can take bounded low/medium-risk actions after policy and proof gates.
- WM verifies action results through native request/result evidence and, where available, DB/client-visible evidence.
- WM reacts to notable events without being prompted, but with cooldowns.
- WM remembers durable player facts across sessions.
- WM can stage small temporary scenes using proven verbs and cleanup rules.
- WM proposes generated content, but DBC/client patch content remains maintenance-gated and never auto-applies while unsafe.
- The panel explains current state and failures without making the operator inspect raw JSON.

Autonomy policy:

- Low/medium-risk verbs may auto-apply only when implemented, enabled, contracted, and live-proven.
- High-risk verbs remain confirm-gated.
- DBC/client patch work remains maintenance-gated.
- The LLM never receives raw SQL, shell, GM commands, or direct mutation power.
- The LLM proposes typed drafts/intents; deterministic Python/C++ validation and policy decide what happens.

## Current Repo Truth

Latest local facts from this handoff session:

- `git status --short`: clean before this handoff document was created.
- Latest commits:
  - `bce5fd7 Add live proof evidence checks`
  - `fd416ff Add runtime heartbeats and live proof checklist`
  - `b7a2fb6 Surface WM timeline summaries`
  - `f97904c Build WM runtime status and proof foundation`
- Full test suite after the latest implementation:
  - `python -m pytest -q`
  - Result: `1172 passed, 31 warnings`
- Status validation:
  - `python -m wm.status --validate`
  - Result: `OK`
- Skill validation:
  - `python scripts\validate_agent_skills.py`
  - Result: `OK: validated skills under .agents/skills`
- Panel summary from `python -m wm.panel summary --json`:
  - `living.catalog`: `PARTIAL`, `1/5 features live-ready`
  - `journal.projector`: `WORKING`
  - `native.contracts`: `WORKING`, `58/100 action kinds contracted`
  - `feature_status.json`: `WORKING`, `18 features tracked`
  - living readiness:
    - `living.rumor`: `true`
    - `living.nemesis`: `false`
    - `living.legend`: `false`
    - `living.patron`: `false`
    - `living.oath`: `false`

Runtime status at handoff:

- `python -m wm.runtime status --json` returns `ok=true`.
- Current services are down: DB/Auth/World/Watcher/Panel/Autoplay all report `not_running`.
- Python runtime marker state exists under `.wm-bootstrap/state/runtime/`.
- Some old stopped markers are present from tests/manual runs; they are not active and not stale.
- Windows process scan has a known warning:
  - `Get-CimInstance Win32_Process` is access denied.
  - Runtime falls back to limited `Get-Process`.
  - This is expected on the current host and is why Python service-owned markers matter.

## High-Level Architecture

### Launcher

Main file: `src/wm/launcher.py`

Purpose:

- Operator-facing Windows GUI for starting and supervising the WM stack.
- Builds visible `cmd /k` runner scripts.
- Prevents duplicate starts by service key using shared runtime status.
- Exposes buttons for core, panel, watcher, autoplay, status refresh, close aux windows, and stop all.

Current state:

- Implemented and tested.
- Long-running Python services get `WM_RUNTIME_MARKER_ROOT`.
- Start commands avoid hidden/minimized windows.
- `Close Aux Windows` and `Stop All WM` clear auxiliary runtime markers.
- Duplicate/stale Python services are blocked before spawning more windows.

Not ready:

- Live operator UX still needs real-world iteration.
- Core startup depends on BridgeLab scripts and actual DB/Auth/World behavior.
- Process stopping still uses Windows command-line matching where unavoidable; marker truth improves display but cannot kill arbitrary external processes by itself.

### Runtime Truth

Main files:

- `src/wm/runtime/status.py`
- `src/wm/runtime/markers.py`

Purpose:

- Shared runtime status object for CLI, launcher, panel, and proof runner.
- Report service name, logical count, PIDs, command hash, health, stale flag, markers, ports, incidents.
- Avoid fragile duplicate reporting from raw Windows process trees.

Current state:

- Implemented.
- CLI: `python -m wm.runtime status --json`
- Panel route: `GET /api/wm/runtime/status`
- Runtime markers for Python services:
  - `watcher`
  - `panel`
  - `autoplay`
- Marker schema includes:
  - `service`
  - `pid`
  - `started_at`
  - `last_seen`
  - `command_key`
  - `command_hash`
  - `health`
  - optional `port`
  - metadata
- Status distinguishes:
  - `not_running`
  - `running`
  - `stale`
  - `duplicate`

Not ready:

- DB/Auth/World do not yet emit service-owned markers. They still depend on process scan/name matching.
- Windows CIM access denied remains a host-level limitation. Do not reintroduce brittle WMIC hacks unless the fix is actually proven.

### Panel

Main files:

- `src/wm/panel/server.py`
- `src/wm/panel/static/index.html`
- `src/wm/panel/static/app.js`
- `src/wm/panel/static/style.css`

Purpose:

- Local operator panel for readiness, session state, autoplay controls, proposal inbox, timeline, incidents, and proof checklist.

Current state:

- Implemented and tested.
- Key APIs:
  - `GET /api/wm/runtime/status`
  - `GET /api/wm/autoplay/status`
  - `GET /api/wm/proofs`
  - `POST /api/wm/proofs/run`
  - `GET /api/wm/timeline`
  - `GET /api/wm/incidents`
- Panel server now emits runtime heartbeat markers.
- Simple dashboard shows `Proof Checklist`.
- Proof checklist shows failing/missing evidence detail.
- Timeline summaries include proofs, runtime incidents, and autoplay journal events.

Not ready:

- UI is functional, not polished.
- Proof execution is still mostly "inspect and record", not a fully automated live scenario runner.
- Need live acceptance screenshots/notes from actual in-game use.

### Autoplay

Main files:

- `src/wm/autoplay/service.py`
- `src/wm/autoplay/state.py`
- `src/wm/autoplay/intent.py`
- `src/wm/autoplay/intent_extract.py`
- `src/wm/autoplay/memory_extract.py`
- `src/wm/autoplay/scene_compose.py`
- `src/wm/autoplay/verification.py`
- `src/wm/autoplay/tools.py`
- `src/wm/autoplay/world_context.py`

Purpose:

- Long-running WM autonomy service.
- Reads recent game events.
- Replies to player chat.
- Extracts typed intents from chat.
- Compiles/dry-runs/applies/blocks actions.
- Sends in-game replies through native bridge action proposals.
- Performs ambient narration on notable events.
- Captures durable conversation memory.
- Composes and parks/runs small scenes.

Current state:

- Implemented across phases 1-5 and covered by tests.
- `autoplay` emits runtime heartbeat markers.
- Direct chat path records `chat` journal entries and `latest_chat`.
- Intent path records pending intent, deed, issues, and latest verification.
- Ambient narration records `ambient_narration`.
- Conversation memory records `conversation_memory`.
- Scene runs record `scene_run`, steps executed, and cleanup status.
- Journal category bug was fixed: canonical journal `kind` is stable; payload-specific kind is preserved as `payload_kind`.

Not ready:

- Needs live proof for the exact current stack.
- Memory persistence depends on DB/journey systems being available in the live environment.
- Scene verbs are only as good as current native bridge support and client visibility.
- Ambient sensors are still limited to currently sensed notable events.

### Native Bridge Actions

Main files:

- `src/wm/sources/native_bridge/action_kinds.py`
- `src/wm/sources/native_bridge/actions.py`
- `src/wm/sources/native_bridge/payload_contract.py`
- native C++ module files under `native_modules/mod-wm-bridge/`

Purpose:

- Deterministic action bus into the live client/server environment.
- Python validates payloads and queues native requests.
- Native module applies supported actions and records results.

Current state:

- `58/100` native action kinds contracted.
- A smaller set is implemented.
- Known useful implemented/proven-ish verbs include:
  - `player_chat_message`
  - `world_announce_to_player`
  - `player_restore_health_power`
  - `debug_ping`
  - `debug_echo`
  - selected player/inventory/quest/world-object verbs
- `player_chat_message` is the key current output path for in-game WM responses.
- `creature_spawn`, `creature_despawn`, `creature_say`, `creature_emote`, and `creature_cast_spell` exist as scene-relevant verbs, but proof status is not fully promoted to broad live-proof confidence.

Not ready:

- Native coverage is still partial.
- `27/100` implemented was the rough prior status; panel currently reports `58/100` contracted, not fully implemented/proven.
- Highest-value missing verbs remain:
  - creature yell/whisper
  - NPC/gossip text override
  - sound
  - weather
  - companion follow/speak/assist
- Every new verb needs Python contract, C++ validation, dry-run/apply behavior, result JSON, tests, and live proof.

### Content And Living World

Main areas:

- content release/gates
- feature status
- living catalog
- rumor/nemesis/legend/patron/oath systems

Current state:

- Content workbench/release gates exist.
- Journal projection is working.
- `living.rumor` is currently live-ready.
- `living.nemesis`, `living.legend`, `living.patron`, and `living.oath` are not live-ready.
- Generated quest/item/spell/content remains behind release packets, dry-run, safe-window, and rollback logic.

Not ready:

- Living world autonomy is not yet a true session director.
- No reliable "observe -> remember -> react -> stage -> reward/propose -> verify" full-session arc has been live-proven.
- DBC/client patch content must stay maintenance-gated.

## What Is Ready

Ready in repo/test sense:

- Launcher command builders and duplicate/stale guard logic.
- Runtime marker schema and status merging.
- Panel runtime/proof/timeline/incidents APIs.
- Proof checklist UI on the simple panel dashboard.
- Proof records with runtime summary, blockers, next actions, evidence checks, evidence refs, and manual evidence notes.
- Autoplay journal/timeline summaries.
- Chat reply path through native action proposals.
- Intent compile/dry-run/apply/confirm structure.
- Ambient narration logic and cooldown tests.
- Conversation memory extraction/persistence path tests.
- Scene composition validation and cleanup requirement.
- Scene run cleanup status recording.
- Autoplay evidence checks for proof packets.
- Test suite green at `1172 passed`.

Ready in live/operator sense:

- Not enough should be claimed yet. Runtime startup, chat action, ambient, memory, and scene all still need a current in-client proof run after starting the actual stack.

## What Is Not Ready

The following are not done:

- Full autonomous local World Master play session.
- One-click "Start All" that reliably brings every dependency to green on every host.
- Live-proof evidence artifacts for the current code after the latest commits.
- Broad native verb set.
- High-confidence scene lane beyond the safe current verbs and cleanup checks.
- Robust in-client visual verification for most verbs.
- Automated replay/evaluation harness for recorded event streams.
- Full session agenda manager that chooses objectives and manages a coherent play arc.
- Living systems beyond rumor.
- Fully polished panel UX.
- DB/Auth/World service-owned markers.
- Complete incident taxonomy for every known failure class.

## Current Proof Model

Proof packet definitions live in `src/wm/proofs/runner.py`.

Current proof kinds:

- `runtime_startup`
- `chat_action`
- `scene`
- `ambient`
- `memory`
- `content`
- `rollback`
- `failure`

Proof records now include:

- `proof_kind`
- `player_guid`
- `checks`
- `blockers`
- `next_actions`
- `runtime_summary`
- `runtime_incidents`
- `evidence_checks`
- `evidence_refs`
- `timeline_refs`
- `manual_evidence`

Important behavior:

- `runtime_startup` can pass automatically from runtime status.
- Live proof kinds remain `manual_required` until their expected evidence appears.
- Evidence-based live proof kinds can now pass when the relevant journal/status artifacts exist:
  - `chat_action`: chat + intent/deed/pending/issue + verification/blocker explanation
  - `ambient`: ambient narration journal
  - `memory`: conversation memory + later chat
  - `scene`: scene run + cleanup status

Do not mark a feature `WORKING` solely because unit tests pass. In-client proof is the standard for autonomous-live claims.

## Next Session Working Order

### Step 1: Start From Clean Runtime

Use launcher first. Avoid manually opening many terminals unless debugging.

Recommended button order:

1. `Stop All WM`
2. `Refresh Status`
3. `Start Core`
4. Wait for DB/Auth/World to settle.
5. `Start Panel`
6. `Start Watcher`
7. `Start Autoplay`
8. `Open Panel`
9. `Refresh Status`

Expected clean target:

- DB/Auth/World: `running (1)`
- Watcher: `running (1)`
- Panel: `running (1)`
- Autoplay: `running (1)`
- No stale/duplicate service incidents.

If watcher/panel/autoplay shows duplicate or stale:

- Press `Close Aux Windows`.
- Press `Refresh Status`.
- Start the specific service once.

If core is duplicated or broken:

- Press `Stop All WM`.
- Confirm visible consoles are closed.
- Start core once.

### Step 2: Run Runtime Startup Proof

From panel:

- Open the simple dashboard.
- Use proof API/UI route as available, or POST:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/wm/proofs/run -ContentType "application/json" -Body '{"proof_kind":"runtime_startup","mode":"dry-run"}'
```

Acceptance:

- Proof status `passed`.
- `runtime_startup` appears green in proof checklist.
- No duplicate/stale required service incidents.

### Step 3: Prove Chat Action

Default proof player remains the configured proof player until panel session selection replaces it. Historically this has been GUID `5408`, but avoid hardcoding that in generic code.

Player flow:

- Enter game with scoped player.
- Join or use WM chat input path.
- Ask for a known safe/proven action, e.g. a simple restore/heal style action.
- If confirm-gated, answer yes.

Acceptance:

- WM replies in-game.
- Autoplay journal records `chat`.
- Autoplay records `deed` or pending/cleared intent or an intent issue.
- `latest_verification` is OK, or a blocker explanation is recorded.
- `chat_action` proof passes or shows exactly which evidence is pending.

### Step 4: Prove Ambient

Trigger one notable event:

- area entry
- quest completion/reward
- level-up
- death
- other sensed notable event supported by current ambient classifier

Acceptance:

- One WM line appears.
- `ambient_narration` journal record exists.
- Cooldown prevents spam.
- `ambient` proof passes or clearly shows pending evidence.

### Step 5: Prove Memory

Player says a durable preference:

- "call me X"
- "I hate undead themes"
- another stable preference supported by memory extraction

Acceptance:

- `conversation_memory` journal record exists and `ok=true`.
- Later chat turn reuses the memory naturally.
- Memory/timeline/panel show the write and later use.
- `memory` proof passes only after later chat evidence exists.

### Step 6: Prove Scene

Ask for a tiny safe scene:

- spawn a simple creature temporarily
- have it say or emote once
- cleanup through `duration_ms` or despawn step

Acceptance:

- `scene_run` journal record exists.
- `steps_executed > 0`.
- `cleanup_status` is one of:
  - `not_required`
  - `temporary_spawn`
  - `despawn_step_planned`
- WM sends completion/failure line.
- `scene` proof passes or reports the failed/missing evidence step.

## Implementation Roadmap After Proof Path

Do not broaden features until the proof path is boring. After runtime/chat/ambient/memory/scene can be repeated, continue in this order:

1. **Replay/Evaluation Harness**
   - recorded event streams
   - fake native coordinator scenarios
   - fake LM Studio scenarios
   - scoring for responsiveness, safety, memory, action correctness, and non-spam behavior

2. **Session Agenda Manager**
   - choose one short objective
   - track progress
   - decide when to speak, react, stage a scene, propose content, or stay quiet

3. **Native Verb Expansion**
   - creature yell/whisper
   - NPC/gossip overrides
   - sound
   - weather
   - companion follow/speak/assist

4. **Persistent Memory Controls**
   - inspectable memory summaries
   - stale-memory controls
   - compaction/summarization policy
   - panel memory view tied to timeline

5. **Living World Lanes**
   - rumor already first
   - then nemesis
   - then legend
   - then patron
   - then oath

6. **Content Autonomy**
   - generated quests/items/spells remain behind release packets
   - safe-window enforcement
   - rollback
   - never auto-apply DBC/client patch content while client/scoped player is active

## Risks And Known Failure Modes

- Windows process scan cannot always read command lines due to CIM access denied.
  - Mitigation: Python services now use heartbeats.
  - Remaining gap: DB/Auth/World markers.
- Duplicate terminal windows can still happen if services are started outside the launcher.
  - Mitigation: launcher detects duplicate/stale for known services and tells operator what button to press.
- Autoplay readiness can be false because DB/SOAP/LM Studio/scoped player is unavailable.
  - Do not debug LLM behavior until readiness is green.
- LM Studio model selection may drift between panel and autoplay state.
  - Use panel settings or `python -m wm.autoplay configure`.
- Scene proof can pass only if the native steps really run and cleanup evidence is recorded.
  - Do not expand scene verbs before this works repeatably.
- Memory proof requires a later chat turn.
  - A memory write alone is not enough.
- Feature status must not overclaim.
  - Repo working, runtime running, and in-client proven are separate states.

## Key Files For Next Session

Runtime/launcher:

- `src/wm/launcher.py`
- `src/wm/runtime/status.py`
- `src/wm/runtime/markers.py`
- `src/wm/runtime/__main__.py`

Panel/observability:

- `src/wm/panel/server.py`
- `src/wm/panel/static/app.js`
- `src/wm/panel/static/index.html`
- `src/wm/observability.py`

Autoplay/proofs:

- `src/wm/autoplay/service.py`
- `src/wm/autoplay/state.py`
- `src/wm/autoplay/verification.py`
- `src/wm/autoplay/scene_compose.py`
- `src/wm/proofs/runner.py`

Native/action contracts:

- `src/wm/sources/native_bridge/action_kinds.py`
- `src/wm/sources/native_bridge/actions.py`
- `src/wm/sources/native_bridge/payload_contract.py`
- `native_modules/mod-wm-bridge/`

Tests most relevant to current sprint:

- `tests/test_runtime_markers.py`
- `tests/test_runtime_status.py`
- `tests/test_launcher.py`
- `tests/test_proofs.py`
- `tests/test_observability.py`
- `tests/test_autoplay.py`
- `tests/panel/test_server_slice.py`
- `tests/test_track3_panel_routes.py`

## Suggested Validation Commands

Run before and after meaningful changes:

```powershell
python -m pytest tests\test_runtime_markers.py tests\test_runtime_status.py tests\test_launcher.py tests\test_proofs.py tests\test_observability.py tests\test_autoplay.py tests\panel\test_server_slice.py -q
python -m pytest -q
python -m wm.status --validate
python scripts\validate_agent_skills.py
python -m wm.runtime status --json
```

Useful panel/runtime probes:

```powershell
python -m wm.panel summary --json
python -m wm.autoplay status --summary
python -m wm.doctor --summary
```

Proof API examples:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/wm/proofs/run -ContentType "application/json" -Body '{"proof_kind":"runtime_startup","mode":"dry-run"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/wm/proofs/run -ContentType "application/json" -Body '{"proof_kind":"chat_action","player_guid":5408,"mode":"dry-run"}'
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/wm/proofs
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/wm/timeline
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/wm/incidents
```

## Do Not Do

- Do not add a broad new feature lane before the live proof path is repeatable.
- Do not hide long-running service windows again.
- Do not claim autonomous features are `WORKING` without in-client proof artifacts.
- Do not give the LLM raw mutation powers.
- Do not auto-apply high-risk or DBC/client patch actions.
- Do not reset or discard user/local changes if the next session finds a dirty tree.

## Best Next Task

The best next task is not another abstraction. It is a live operator pass:

1. Start the stack from the launcher.
2. Make `runtime_startup` pass.
3. Run one chat action proof.
4. Run one ambient proof.
5. Run one memory proof.
6. Run one scene proof.
7. Save the proof records and panel timeline.
8. Only then decide which missing blocker deserves implementation.

If a proof fails, fix the specific blocker surfaced by `evidence_checks`, `next_actions`, and `incidents`. Keep the scope narrow.
