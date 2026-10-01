Status: WORKING
Last verified: 2026-06-25
Verified by: Codex
Doc type: handoff

# Next Session Handoff - 2026-06-25

This handoff is a compact operating brief for a fresh Codex/LLM session in
`D:\WOW\wm-project`. It is not a replacement for the recovery handoff or the
platform docs. Its job is to keep the next model aligned, make the tool plan
explicit, and prevent it from drifting into a new architecture.

## Prime directive

WM is a bounded, local, external-first World Master for AzerothCore 3.3.5a. The
correct direction is not a generic AI NPC, a freeform game master, or a new
middleware stack. Keep the existing split:

- Python owns decisions, state, validation, publishing, rollback, policy,
  prompt/context packaging, audit, and operator workflow.
- Native AzerothCore modules own sensing, scoped typed actions, and shell-bound
  runtime spell behavior.
- The LLM is advisory and schema-bound. It may draft proposals, but it must not
  directly mutate SQL, configs, shell commands, GM commands, or game state.
- Gameplay-facing claims require live proof. Repo/API tests can make a lane
  `WORKING` at repo level, but unproven in-client behavior stays `PARTIAL`.

## Read order for the next session

Read these before non-trivial work:

1. `AGENTS.md`
2. `docs/1_HANDOFF.md`
3. `docs/README_OPERATIONS_INDEX.md`
4. `docs/CODEX_WORKING_RULES.md`
5. `docs/AGENT_SKILLS_LIFECYCLE.md`

Then read only the task-specific docs. Prefer current-state docs and
postmortems over roadmap/design notes when they conflict.

## Current trust model

Do not trust old prose status without re-verification. Start by running:

```powershell
git status --short
git branch --show-current
git log --oneline -5
python -m wm.status --validate
python scripts/validate_agent_skills.py
python -m wm.sources.native_bridge.contracts_cli
```

Use `python -m pytest -q` before claiming broad repo health if the host is
ready. Use focused tests first while iterating.

## Immediate operating plan

1. Re-baseline the tree and confirm whether there is user-owned dirty work.
2. Identify the narrow task and map it to an existing WM path.
3. Select the narrowest repo-local skill.
4. Read the relevant code/docs before proposing architecture.
5. Make one reversible slice.
6. Verify with focused tests, then broader tests if shared behavior changed.
7. Update docs only where behavior, workflow, or proof status changed.
8. End with exact labels: `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`.

## Repo-local skills to use

Use `docs/AGENT_SKILLS_LIFECYCLE.md` as the router.

- `$wm-workflow`: docs, handoffs, cleanup, tests, workflow, general code.
- `$wm-live-bridge-lab`: BridgeLab, watcher, native bridge, live proof, player
  scope, lab cleanup, runtime readiness.
- `$wm-content-release`: quests, items, spells, shells, arcs, scenes, context
  packs, LLM proposal contracts, release packets.

There are more narrow skills in `.agents/skills/` for repeatable operations
such as creating quests/items/spells, reserving slots, granting/removing
content, rollback, client patch builds, reloads, native smoke tests, context
packs, scenes, player announcements, and journal writes. Prefer those over
ad hoc commands when the task matches.

Validate skill metadata after skill edits:

```powershell
python scripts/validate_agent_skills.py
```

## Tool plan

Use these tools and methods deliberately:

- `git status --short`, `git diff`, and `git log`: protect user changes and
  establish the real baseline.
- `.\.wm-bootstrap\tools\ripgrep\rg.exe` or `.\.wm-tools\rg.exe`: preferred
  search on this Windows host if bare `rg` fails with access denied.
- `apply_patch`: manual source/doc edits. Keep edits scoped and ASCII unless a
  file already needs another encoding.
- `python -m pytest ...`: focused and full repo verification.
- `python -m wm.*` CLIs: status, doctor, contracts, content, context, proof,
  rollback, and runtime operations.
- BridgeLab batch wrappers: use repo-owned launchers such as
  `start-bridge-lab-all.bat`, `start-bridge-lab-watch.bat`,
  `status-bridge-lab-watch.bat`, and `stop-bridge-lab-watch.bat`.
- Browser/in-app browser tools: use for panel visual smoke when local browser
  access works; if not, record API/HTTP proof and keep UI proof `PARTIAL`.
- Web browsing: use only when the user asks for current external information or
  when a dependency/API fact may have changed; prefer primary docs.

Avoid direct DB edits, raw SQL mutation, raw GM commands, detached watcher
PowerShell, one-off config edits, and hidden direct LLM mutation lanes.

## Architecture guardrails

- Extend `src/wm/`, `control/`, `native_modules/mod-wm-bridge/`, and
  `native_modules/mod-wm-spells/` before inventing a subsystem.
- New native capability means a typed `action_kind` on the existing action bus,
  not a parallel executor.
- Visible abilities use WM-owned shell-bank spell IDs. Never make stock spell
  IDs permanent WM carriers.
- Separate client truth from server truth before spell, item, UI, or shell work.
- AzerothCore tables are mechanical truth; `wm_*` tables are memory, policy,
  provenance, and rollback. Do not add custom columns to core AC tables.
- Fresh visible IDs are safer than repairing dirty live IDs. Retire broken IDs
  in the registry and publish replacements through owned lanes.
- After three failed attempts on the same approach, stop and write the
  structural reason before changing more code.

## Anti-steer rules for future models

If the next model starts drifting, force it through this checklist:

1. What existing WM module, CLI, registry, action bus, shell bank, or release
   pipeline handles this already?
2. What is the proof label now: `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`?
3. Is this repo proof, API proof, native proof, DB proof, or in-client proof?
4. Does this require client truth, server truth, or both?
5. Is any proposed mutation schema-bound, audited, scoped, reversible, and
   dry-run-able?
6. Is the model inventing a new architecture because it has not read the old
   one?
7. Is it trying to call gameplay done without BridgeLab or in-client evidence?

Hard stop if the answer is unclear for any mutation that touches live content,
native actions, spells, items, quests, player state, or runtime config.

## Forbidden shortcuts

- Do not add freeform SQL, GM-command, shell-command, config-edit, or direct
  LLM mutation lanes.
- Do not bypass the native bridge action bus for production behavior.
- Do not reuse stock spell IDs as permanent carriers.
- Do not call a browser/UI smoke failure irrelevant; mark visual proof
  `PARTIAL` if it was not actually seen.
- Do not claim gameplay `WORKING` from tests alone.
- Do not rewrite docs to make status sound better than evidence supports.
- Do not revert user-owned dirty files unless explicitly told to.

## Definition of done for the next session

A good next session ends with:

- a short summary of files changed;
- exact verification commands and results;
- proof labels for each touched area;
- remaining live-proof or operator-gated gaps;
- no hidden architecture drift;
- no unmentioned dirty work.

If the task is exploratory, finish by updating the relevant status/handoff or
postmortem doc with what is known, what remains unknown, and the next concrete
command to run.
