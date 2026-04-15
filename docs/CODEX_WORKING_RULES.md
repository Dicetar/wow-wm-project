Status: WORKING
Last verified: 2026-04-15
Verified by: Codex
Doc type: reference

# Codex Working Rules

This file is the repo-specific working prompt for future Codex sessions.

Use it with:

- [../AGENTS.md](../AGENTS.md)
- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)
- [Documentation Index](README_OPERATIONS_INDEX.md)

## Purpose

The goal is not to make the agent generic or polite. The goal is to keep the WM repo coherent, technically honest, and recoverable between sessions.

## Research protocol

### 1. Read the real code before proposing architecture

Before proposing a new subsystem, inspect the existing ones first:

- `src/wm/`
- `control/`
- `native_modules/mod-wm-bridge/`
- `native_modules/mod-wm-spells/`

Do not propose a greenfield router, runner, registry, or middleware layer if the repo already has one that can be extended.

### 2. Split client truth from server truth before spell work

Before implementing or proposing any spell-related change, answer these two questions explicitly:

1. Does the client need to know this spell exists?
2. Does the server need to know this spell exists?

Rules:

- If the client must show the spell in the spellbook, action bar, tooltip, or icon, a client shell or client patch is required.
- If the work is server-only and invisible to the player, a server-side debug or action path may be enough.
- If you skip client work for a test, label it `testing only, not shippable`.

### 3. State assumptions before risky native work

Before changing native code for spells, creatures, pets, or runtime hooks, write down:

- which carrier, entry, chassis, or hook is being used
- what stock behavior that thing already has
- why it is safe or why it is only a temporary lab path
- how the test state will be cleaned up

If you cannot state those assumptions, do not implement yet.

## Architecture protocol

### 1. Keep the WM split intact

Python owns:

- reasoning
- state machines
- cooldowns
- scene composition
- proposal validation
- prompt/perception packaging

C++ owns:

- event sensing
- atomic action execution
- runtime safety checks
- shell-bound native ability behavior

Do not move narrative logic or long-lived state machines into C++.

### 2. Extend the existing action bus

The atomic execution surface is `wm_bridge_action_request`.

Rules:

- new native capability means a new `action_kind`
- do not build a parallel C++ action runner
- do not bypass the bus with hidden one-off executors unless the work is clearly lab-only and documented as such

### 3. Think in triggers and scenes

When proposing wild features, describe them as:

1. trigger or event
2. Python-side decision and state
3. atomic action sequence
4. client requirement level

Do not start from "what stock spell can I hijack."

### 4. Use WM-owned spell identities

Production WM abilities use:

- WM shell-bank spell IDs
- WM-owned behavior bindings
- `mod-wm-spells`

Do not use stock live spell IDs as permanent carriers.

## Testing protocol

### 1. Clean summon and pet state before each test

Mandatory pre-test checklist for summon or pet work:

```text
[ ] character_pet rows for the test player are clean
[ ] character_spell has no stale carrier grants
[ ] worldserver log is known-clean or noted
[ ] lab worldserver restarted after native code or conf changes
[ ] test character logged in fresh after restart
```

If any item fails, stop and clean the lab first.

### 2. Change one variable at a time

Do not change carrier, creature entry, scale, stat model, and save logic in one test pass. If a test changes more than one meaningful variable, it is not diagnostic.

### 3. Run regression checks when touching spells or pets

If you touch summon, creature, or pet behavior, regression-test at least:

- stock warlock summons
- hunter pet baseline if the chassis overlap matters

If you cannot run the regression, document it as untested.

### 4. Promote proven tools into release lanes

When a schema, tool, or behavior is proven `WORKING` and operators will use it repeatedly, create a release lane that does the same action without the diagnostic preflight stack.

Rules:

- Keep the test/debug lane for validation, preflight, dry-run, polling, and detailed evidence.
- Add a separate release command or explicit release flag for the proven path.
- Release lanes must submit the known-good action directly, fail fast on real runtime errors, and avoid hidden dry-runs, player lookups, schema probes, and default wait loops.
- Release lanes must document exact prerequisites. If a prerequisite is not proven, the lane is `PARTIAL`, not `WORKING`.
- Do not use release lanes for `PARTIAL`, `UNKNOWN`, or structurally dirty lab states.

### 5. End each session with hard labels

Every changed component must be labeled as one of:

- `WORKING`
- `PARTIAL`
- `BROKEN`
- `UNKNOWN`

Do not use vague labels like "almost" or "close enough."

## Documentation protocol

### 1. Separate status, design, how-to, reference, and postmortem

Use the repo doc types consistently:

- `status`: current supported state
- `handoff`: current system map and operator guidance
- `howto`: exact commands plus verify steps
- `reference`: contracts, tables, interfaces, layouts
- `design`: roadmap or intended architecture
- `postmortem`: failed approach, evidence, root cause, retirement decision
- `adr`: durable architecture decision record

### 2. Use metadata headers

Important docs should begin with:

```text
Status: WORKING | PARTIAL | DESIGN_ONLY | BROKEN | STALE | UNKNOWN
Last verified: YYYY-MM-DD
Verified by: human | Codex | unknown
Doc type: handoff | howto | reference | design | postmortem | adr | status
```

### 3. Docs describe current truth

If something worked once but is not proven now, do not write it as present-tense fact.

Current-state docs must say:

- what is supported
- what is partial
- what is blocked
- what is retired

### 4. Update the surviving context docs

After meaningful work, update the relevant current-state docs before ending the session:

- `docs/WM_PLATFORM_HANDOFF.md`
- feature-specific status docs
- postmortem docs if something failed structurally

## Stop conditions

### 1. Three failures means stop

If the same approach fails three times with different parameters, stop and identify the shared structural cause.

### 2. "Just one more tweak" is a warning

If the foundation is not stable, do not pile tuning work on top of it.

### 3. Dirty labs are not neutral

If the lab might be polluted by stale rows, config drift, or local overrides, treat it as dirty and reset it before trusting any result.

## Windows detached process rule

For long-running detached WM watchers on this Windows host:

- do not use PowerShell `Start-Process` when reliable PID capture and redirected logs matter
- use the repo-owned `System.Diagnostics.ProcessStartInfo` pattern instead
- for long-running watchers launched from Codex shell commands, set `UseShellExecute = $true`; `UseShellExecute = $false` can keep the child watcher attached to the shell command lifetime even when stdout/stderr are redirected
- do not report `started=true` until:
  - the process object is non-null
  - the PID is non-empty
  - the process is still alive after a short startup delay

If this rule is violated and the launch fails, record it in a postmortem instead of retrying the same pattern blindly.

## Creativity rules

Creativity in this repo means reusable leverage, not random cleverness.

Preferred pattern:

- extend the existing bus, control registry, shell bank, or workbench
- add a reusable primitive
- compose scenes from atomic actions
- keep the same contract available to manual and future LLM flows

Avoid:

- one-off carrier hacks
- duplicate middleware
- solving a broad problem with a single stock spell trick

## Feature feasibility filter

Use this before proposing implementation:

| Tier | Meaning | Typical examples |
| --- | --- | --- |
| `T1` | Server only | faction changes, aura apply/remove, creature spawn, stat changes, teleports |
| `T2` | Server plus existing client assets | reuse existing visuals or spell effects with custom server logic |
| `T3` | Client patch required | new visible spellbook abilities, new tooltips, stable custom shells |
| `T4` | Client asset or UI work | new art, new model assets, custom interface elements |
| `NOT FEASIBLE` | Not realistic in stock 3.3.5a | binary-client changes, fake physics systems, unsupported client behavior |

If the feature is `T3` or `T4`, document that immediately instead of pretending a server-only workaround is production-safe.
