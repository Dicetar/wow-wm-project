# WM Next Session Handoff - 2026-05-27

Status: active WIP handoff  
Repository: `D:\WOW\wm-project`  
Branch: `main`  
Current priority: make WM playable without Codex actively driving it

## Executive Summary

The project is now past "platform skeleton" and into "local playable operator" work.
The important shift is that WM must run as a visible, understandable Windows app
stack while the player is in-game. The player should not need Codex open, should
not need to remember five commands, and should not need hidden background
processes.

The current local code has strong WIP progress on:

- autoplay service commands and state;
- LM Studio model configuration from panel/autoplay;
- direct in-game WM chat via `WM` channel and `towm` fallback;
- LLM world-context packing for chat;
- native `player_chat_message` action so replies can appear in chat instead of
  world announcements;
- panel Simple/Advanced controls;
- chat context reset from panel and `forget context` in chat;
- bounded model tool visibility through `wm.autoplay.tools`;
- broader tests around autoplay, native bridge actions, addon chat source, and
  panel routes.

The big current issue is not missing test coverage. It is product integration:
launching, readiness, live service orchestration, and making the LLM consistently
see enough world state to feel like the World Master.

## Repo Truth At Handoff

Latest verified local facts:

- `git status --short --branch`: `main...origin/main [ahead 1]`
- Latest local commit: `f73a50f feat(bounty): use rolling kill window cooldowns`
- `origin/main`: `d527314 fix(autoplay): harden playable startup`
- There is a large uncommitted WIP batch: about 36 modified files plus several
  untracked files.
- Full tracked test suite was run after the WIP changes:
  - `python -m pytest -q`
  - Result: `1028 passed, 31 warnings`
- Status validation:
  - `python -m wm.status --validate`
  - Result: `OK`
- Skill validation:
  - `python scripts\validate_agent_skills.py`
  - Result: `OK: validated skills under .agents/skills`
- Panel summary:
  - `living.catalog`: `PARTIAL`, `1/5`
  - `journal.projector`: `WORKING`
  - `native.contracts`: `WORKING`, `58/100` action kinds contracted
  - `feature_status.json`: `WORKING`, `17` tracked features
- Explicit BridgeLab doctor with `33307/7879`:
  - DB is reachable.
  - SOAP is down: `http://127.0.0.1:7879/` refused.
  - Result: `NOT READY: 1 FAIL, 0 UNKNOWN, 8 checks`
- Autoplay state at handoff:
  - `status=paused`
  - `running=true`
  - `paused=true`
  - `player_guid=5408`
  - `readiness=false`
  - `llm=false`
  - `model=kansensakura-erosion-rp-12b-heretic-i1`
  - `llm_enabled=true`
  - `wm_chat=true`
  - `chat_epoch=2`
  - `lanes=chat`
  - `drafts=1`
  - `chat=34`
  - `issues=35`

## Dirty Worktree

Do not reset or casually discard this work. It is the active WIP toward LLM
playability.

Modified files:

- `control/actions/native/native_bridge_action.json`
- `docs/SETUP_COMPLETE.md`
- `docs/WM_AUTOPLAY_LLM_PLAYABILITY.md`
- `docs/native-bridge-action-bus.md`
- `native_modules/mod-wm-bridge/data/sql/world/base/wm_bridge_base.sql`
- `native_modules/mod-wm-bridge/src/wm_bridge_environment_actions.cpp`
- `native_modules/mod-wm-bridge/src/wm_bridge_player_script.cpp`
- `src/wm/autoplay/__main__.py`
- `src/wm/autoplay/llm.py`
- `src/wm/autoplay/service.py`
- `src/wm/autoplay/state.py`
- `src/wm/content/release.py`
- `src/wm/events/models.py`
- `src/wm/llm/lmstudio.py`
- `src/wm/llm/prompts.py`
- `src/wm/panel/schemas.py`
- `src/wm/panel/schemas/catalog.json`
- `src/wm/panel/server.py`
- `src/wm/panel/state.py`
- `src/wm/panel/static/app.js`
- `src/wm/panel/static/index.html`
- `src/wm/panel/static/style.css`
- `src/wm/sources/addon_log/adapter.py`
- `src/wm/sources/addon_log/models.py`
- `src/wm/sources/addon_log/resolver.py`
- `src/wm/sources/native_bridge/action_kinds.py`
- `src/wm/sources/native_bridge/adapter.py`
- `start-wm-playable.bat`
- `tests/panel/test_llm_client.py`
- `tests/panel/test_schema_catalog.py`
- `tests/panel/test_server_slice.py`
- `tests/test_addon_log_source.py`
- `tests/test_autoplay.py`
- `tests/test_native_bridge_actions.py`
- `tests/test_native_bridge_source.py`
- `wow_addons/WMBridge/WMBridge.lua`

Untracked files:

- `docs/WM_MAIN_DESIGN_DOCUMENT.md`
- `docs/NEXT_SESSION_HANDOFF_2026_05_27.md`
- `native_modules/mod-wm-bridge/data/sql/world/updates/2026_05_26_00_wm_bridge_player_chat_message.sql`
- `src/wm/autoplay/tools.py`
- `src/wm/autoplay/world_context.py`
- `start-wm-panel-app.bat`

Important note: `start-wm-playable.bat` currently launches autoplay with a
hidden PowerShell `Start-Process ... -WindowStyle Hidden`. The user explicitly
rejected stealth/hidden service launches and wants visible windows. Treat that
as a product bug, not as final behavior.

## Main Goals For Next Session

### 1. Build One Visible WM Launcher App

The user wants one Windows GUI app that launches and supervises the local WM
play stack. This is now the top product objective.

Required behavior:

- One GUI window, probably Python `tkinter` to avoid new dependencies.
- Checked-in entrypoint:
  - `python -m wm.launcher`
  - `start-wm-launcher.bat`
- The app must launch services in visible windows:
  - BridgeLab MySQL
  - authserver
  - worldserver
  - native BridgeLab watcher
  - autoplay
  - control panel server
  - optional browser/panel window
- No hidden service windows.
- No `Start-Process -WindowStyle Hidden` for these user-facing runtime services.
- Prefer visible `cmd /k` windows with clear titles, for example:
  - `WM BridgeLab MySQL`
  - `WM Auth Server`
  - `WM World Server`
  - `WM Native Watcher`
  - `WM Autoplay`
  - `WM Panel Server`
- The launcher should show status in the GUI:
  - DB port/profile
  - SOAP readiness
  - auth/world process hint
  - watcher running
  - autoplay running/paused
  - LM Studio health/model
  - panel URL
  - active player GUID
  - latest blocker
- Include buttons:
  - Start All Visible
  - Start DB
  - Start Server Menu or Start Auth/World
  - Start Watcher
  - Start Autoplay
  - Start Panel
  - Open Panel
  - Pause/Resume Autoplay
  - Stop Autoplay
  - Stop Watcher
  - Run Doctor
  - Refresh Status

Implementation guidance:

- Add pure command-builder functions and test them.
- The tests should assert that generated launch commands do not contain:
  - `WindowStyle Hidden`
  - `/MIN`
  - `start-wm-playable.bat` for autoplay launch
- The GUI can still use internal status subprocesses for quick status reads.
  The "visible windows" rule is mainly about long-running services.
- Do not overbuild process killing. For auth/world, closing their visible
  windows is acceptable initially unless a safe stop helper already exists.
- Use existing scripts where they are already visible:
  - `start-bridge-lab-mysql.bat`
  - `start-bridge-lab-server.bat`
  - `start-bridge-lab-watch.bat`
  - `stop-bridge-lab-watch.bat`
  - `stop-wm-playable.bat`
- For autoplay, launch Python directly in a visible console instead of using the
  current hidden `start-wm-playable.bat` behavior.

### 2. Fix Runtime Readiness Before More LLM Work

Current blocker:

- BridgeLab DB works on `33307`.
- SOAP `7879` is down.
- Autoplay reports `readiness=false`.
- LM Studio health was false at the last status check.

Next session should first bring runtime to a boring known state:

```powershell
$env:WM_WORLD_DB_PORT = "33307"
$env:WM_CHAR_DB_PORT = "33307"
$env:WM_SOAP_PORT = "7879"
$env:WM_SOAP_ENABLED = "1"
python -m wm.doctor --summary
python -m wm.autoplay status --summary
```

Target:

- explicit doctor is `8/8 WORKING`;
- player `5408` is online/scoped or the launcher clearly says why not;
- LM Studio `/v1/models` is reachable;
- configured model in panel and autoplay state match;
- autoplay is running and unpaused only when all blockers are visible.

How to tackle:

- Start MySQL first.
- Start auth/worldserver and confirm SOAP config uses `7879`.
- If SOAP refuses, inspect BridgeLab worldserver console and config, not Python.
- Confirm native bridge scope includes `5408`.
- Confirm LM Studio server is listening on `http://localhost:1234/v1`.
- Use `python -m wm.autoplay configure --llm-model <model> --summary` to force
  state if panel and runtime disagree.

### 3. Make Direct WM Chat Reliable

The desired player behavior:

- Join custom channel: `/join WM`
- Type normally in that channel.
- WM answers in that channel as `WorldMaster` or equivalent native chat sender.
- Fallback phrase `towm <message>` should still work in ordinary chat.
- `forget context` should reset chat history and get an acknowledgement.
- No LLM reply should be delivered as a world announcement unless explicitly
  testing the old announcement action.

Current WIP implementation pieces:

- `wow_addons/WMBridge/WMBridge.lua` now recognizes WM channel traffic and
  `towm` fallback.
- Native bridge has a new `player_chat_message` action kind and SQL update.
- Autoplay ingests native/addon `wm_chat` events.
- Autoplay direct chat replies use `_chat_action_proposal` with
  `native_action_kind=player_chat_message`.
- Panel exposes chat context epoch and reset button.
- `forget context`, `forget chat context`, and `reset chat context` are handled
  by the service.

Known symptoms to retest:

- User previously saw a world announcement even after asking for chat output.
- User later saw correct `[7. WM] [Astel]: ...` input, but replies became
  inconsistent/silent.
- Model changes from panel previously did not reliably affect running autoplay.

How to tackle:

- Verify the native SQL update is applied in BridgeLab:
  `2026_05_26_00_wm_bridge_player_chat_message.sql`
- Verify the native module was rebuilt/staged after the C++ action changes.
- Verify `control/actions/native/native_bridge_action.json` includes
  `player_chat_message`.
- Query recent `wm_bridge_action_request` rows after chat:
  confirm action kind is `player_chat_message`, not `world_announce_to_player`.
- Query recent `wm_bridge_event` rows:
  confirm WM channel chat is recorded with speaker GUID/name.
- If action kind is correct but output is wrong, fix native execution in
  `wm_bridge_environment_actions.cpp`.
- If no reply appears, inspect autoplay issues in
  `.wm-bootstrap/state/autoplay`.
- If LM Studio is slow, raise cooldown or run `chat` lane only.

### 4. Make The LLM Actually See The World

The user's core complaint is correct: a model that cannot identify the speaking
character or inspect current world facts does not feel like a World Master.

Current WIP:

- `src/wm/autoplay/world_context.py` builds a bounded read-only context for
  direct chat.
- It includes speaker facts, current character facts, recent WM chat, recent
  bridge events, recent native actions, latest native snapshot, and compact
  session context.
- `src/wm/autoplay/tools.py` exposes a compact tool manifest to the panel and
  model prompt.
- The model still does not call tools. It sees a snapshot. Deterministic Python
  remains the only tool executor.

Next target:

- Every direct WM chat prompt should send a compact context bundle containing:
  - speaker GUID;
  - speaker name;
  - current area/map/position if available;
  - active auras or latest relevant native snapshot if available;
  - recent kills/interactions;
  - recent WM channel conversation after current context epoch;
  - active proposals/issues;
  - allowed output/action verbs.

How to tackle:

- Add tests that feed a fake `wm_bridge_event` chat row and fake character DB
  row, then assert the prompt context contains `speaker_name`.
- Add tests that `forget context` filters or marks old chat as stale.
- Keep context small. Do not dump entire DBs into prompts.
- If a fact is deterministic, answer it deterministically before calling the
  model. Current helper `_deterministic_chat_fact_reply` is the right pattern.
- The model should never receive raw SQL credentials, shell commands, or direct
  DB mutation authority.

### 5. Stabilize Model Configuration

Current state says autoplay config model is:

```text
kansensakura-erosion-rp-12b-heretic-i1
```

But the user previously saw Mistral Nemo still being launched after changing
the panel model.

Likely causes:

- Existing hidden autoplay process started with an older `--llm-model` CLI arg.
- Panel setting updated `wm.panel` settings but not autoplay state. A WIP fix
  now syncs panel LLM settings into `AutoplayStateStore`.
- `start-wm-playable.bat` can still pass `-LlmModel` and override state.
- Multiple old autoplay processes may exist.

How to tackle:

- Add launcher status showing:
  - panel saved model;
  - autoplay state model;
  - runtime CLI override model, if detectable;
  - LM Studio loaded/available models.
- Make the visible launcher stop old autoplay before starting a new one, or at
  least warn when PID already exists.
- Prefer one source of truth:
  - panel/autoplay state should be the runtime model;
  - CLI args should be temporary overrides visible in status.
- Keep tests for `/api/settings` syncing model/base URL into autoplay config.

### 6. Convert Panel Into A Separate App Surface

The user wants browser-ish panel behavior moved into a separate window/app, and
also wants two modes:

- Simple mode: slick UX, dropdowns where possible, publishing and LLM controls.
- Advanced mode: existing operator/debug surface.

Current WIP:

- `start-wm-panel-app.bat` opens the panel in Edge/Chrome app mode.
- Panel static files have Simple/Advanced mode work.
- `GET /api/wm/tools` is available.
- Panel has controls for autoplay model, lanes, chat context reset, generate,
  pause/resume.

Current issue:

- `start-wm-panel-app.bat` starts the server minimized (`/MIN`) and is still a
  browser-app wrapper, not a true launcher.

How to tackle:

- Keep the panel browser app as acceptable short-term UI.
- Build the new launcher as the actual Windows control app.
- The launcher should have a button to open the panel app/window.
- Do not spend the whole next session redesigning CSS. The operational launcher
  is more important.
- Simple panel mode should focus on:
  - player GUID/session;
  - ready/not ready;
  - model select;
  - temperature/top-p/max tokens;
  - chat lane on/off;
  - lanes dropdown/checklist;
  - reset context;
  - last reply;
  - latest blockers;
  - issue list.

### 7. Commit The WIP In PR-Sized Slices

The current WIP is too large to land as one opaque commit unless the next
session only does final cleanup and all tests remain green.

Recommended slices:

1. Native chat action slice:
   - native SQL update;
   - native C++ `player_chat_message`;
   - action registry;
   - native tests/docs.
2. Addon/native WM chat ingestion slice:
   - addon channel/prefix changes;
   - addon log source/resolver changes;
   - event model changes;
   - tests.
3. Autoplay LLM chat/world-context slice:
   - `world_context.py`;
   - `tools.py`;
   - service chat flow;
   - state/context reset;
   - tests.
4. Panel controls slice:
   - panel endpoints;
   - Simple/Advanced UI;
   - model sync;
   - reset context button;
   - tests.
5. Visible launcher slice:
   - `wm.launcher`;
   - `start-wm-launcher.bat`;
   - docs/tests;
   - remove or deprecate hidden launcher behavior.

If time is short, create the visible launcher slice first because it directly
answers the user's latest operational blocker.

## Current And Near Issues

### Issue: SOAP Down

Impact:

- Autoplay readiness false.
- Apply/verify loops cannot be trusted.
- Direct chat action may dry-run but not reliably live-apply.

Tackle:

- Start BridgeLab auth/worldserver visibly.
- Confirm SOAP config and port `7879`.
- Run explicit doctor.
- Keep this blocker visible in launcher and panel.

### Issue: Hidden Launchers Conflict With User Preference

Impact:

- User cannot see what is running.
- Hard to debug stuck autoplay/model calls.
- Violates explicit "all visible windows, no stealth stuff" request.

Tackle:

- Add visible launcher app.
- Change or deprecate `start-wm-playable.bat`.
- Make all long-running runtime processes visible by default.
- Keep logs, but do not make logs the only evidence of life.

### Issue: Direct Chat Still Needs Live Proof

Impact:

- The core player-facing LLM interaction is not yet proven stable.

Tackle:

- Rebuild/stage native bridge.
- Apply SQL update.
- Start visible stack.
- Join `/join WM`.
- Type in WM channel:
  - `Who am I?`
  - `Where am I?`
  - `forget context`
  - `What happened recently?`
- Verify replies are chat messages, not announcements.
- Verify context contains actual speaker facts.

### Issue: LLM Can Produce Flavor But Not Yet Rich Control

Impact:

- It can chat and draft bounded proposals, but does not yet feel like a full
  game master.

Tackle:

- Expand context snapshots.
- Expose current tool/action manifest in panel and prompt.
- Add controlled action affordances:
  - speak to player;
  - small scene message;
  - inspect recent events;
  - propose quest/item/spell/scene;
  - park issue;
  - request human approval for medium/high risk.
- Do not let the model execute tools. Python executes only validated proposals.

### Issue: Model Churn And Slow Generations

Impact:

- Mistral Nemo was slow and sometimes hit LM Studio channel errors.
- User is testing other 12B-ish RP/instruct models.
- Autoplay can spam drafts if lanes are too broad.

Tackle:

- Default playable mode to `chat` lane only.
- Use `--llm-events-per-tick 1`.
- Keep cooldowns conservative for scene/action generation.
- Show active model and chat epoch in launcher and panel.
- Add a "Reset Model Context" button and `forget context` chat phrase, already
  WIP.

### Issue: Large Service File

Impact:

- `src/wm/autoplay/service.py` is now very large, around 2k+ lines.
- It mixes runtime service loop, LLM chat, context, policy, publish compilation,
  and native proposal execution.

Tackle:

- Do not refactor before the launcher/live proof unless needed.
- After live proof, split carefully:
  - `chat_runtime.py`
  - `policy.py`
  - `proposal_compile.py`
  - `runtime_apply.py`
  - `watchers.py`
- Keep tests green between each split.

### Issue: Line Ending Warnings

Impact:

- Git reports LF/CRLF normalization warnings across several files.
- Not a product blocker, but can make diffs noisy.

Tackle:

- Do not churn line endings casually.
- If committing, review diff carefully.
- Leave broad `.gitattributes` changes for a dedicated hygiene pass.

## Suggested Next Session Order

1. Do not run `git reset` or discard WIP.
2. Inspect `git status --short --branch`.
3. Run:

```powershell
python -m pytest -q
python -m wm.status --validate
python scripts\validate_agent_skills.py
```

4. Build `wm.launcher` with visible service windows.
5. Add launcher tests for command generation and no hidden/minimized flags.
6. Add `start-wm-launcher.bat`.
7. Use the launcher to start DB/auth/world/watcher/panel/autoplay visibly.
8. Fix SOAP readiness if still failing.
9. Live-test direct WM chat:

```text
/join WM
Who am I?
Where am I?
forget context
What can you see?
```

10. Confirm chat replies use `player_chat_message`.
11. Commit one clean slice or leave a clear WIP status if live proof is blocked.

## Commands Worth Keeping Nearby

Status:

```powershell
git status --short --branch
python -m wm.autoplay status --summary
python -m wm.panel summary
python -m wm.status --validate
python scripts\validate_agent_skills.py
```

Explicit BridgeLab doctor:

```powershell
$env:WM_WORLD_DB_PORT = "33307"
$env:WM_CHAR_DB_PORT = "33307"
$env:WM_SOAP_PORT = "7879"
$env:WM_SOAP_ENABLED = "1"
python -m wm.doctor --summary
```

Autoplay config:

```powershell
python -m wm.autoplay configure --llm-enabled --llm-chat-enabled --llm-lanes chat --summary
python -m wm.autoplay configure --llm-model kansensakura-erosion-rp-12b-heretic-i1 --summary
python -m wm.autoplay pause --summary
python -m wm.autoplay resume --summary
python -m wm.autoplay stop --summary
```

Direct chat CLI smoke:

```powershell
python -m wm.autoplay chat --player-guid 5408 --message "Who am I?" --summary
python -m wm.autoplay chat --player-guid 5408 --message "forget context" --summary
```

Panel:

```powershell
python -m wm.panel serve --host 127.0.0.1 --port 8765
```

Current hidden helper to avoid relying on as final behavior:

```powershell
.\start-wm-playable.bat -PlayerGuid 5408
```

It works as a background helper but conflicts with the visible-window launcher
goal.

## Acceptance Criteria For The Next Real Milestone

The next milestone is not "more features." It is "playable without Codex."

Minimum acceptance:

- One visible GUI launcher starts the whole local stack.
- No required runtime service is hidden.
- Launcher shows readiness blockers without reading logs manually.
- Explicit doctor reaches `8/8 WORKING`.
- LM Studio model selected in panel/launcher is the model used by autoplay.
- `/join WM` plus normal channel chat produces WM replies in chat.
- `forget context` works from panel and in-game chat.
- WM can answer identity/location/recent-action questions from real context,
  not generic model guessing.
- Failed readiness or failed apply parks a visible issue.
- Full tests remain green.

## Product North Star

The player should be able to:

1. Open one WM launcher.
2. Press Start All.
3. Log into WoW.
4. Join `WM`.
5. Talk to World Master in-game.
6. See WM react to actual events.
7. Let WM draft and apply only low-risk safe actions.
8. Pause, inspect, reset context, or stop everything from the launcher/panel.

The LLM should feel like an in-world operator, but it must remain bounded:

- it sees curated world context;
- it returns chat or typed drafts;
- deterministic Python validates and applies;
- native code executes only contracted actions;
- rollback and audit remain mandatory for real mutations.

That is the line between "playable WM" and "random model attached to a private
server."
