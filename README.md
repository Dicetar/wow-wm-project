# wow-wm-project

World Master for AzerothCore 3.3.5a: an external-first content and reaction platform that publishes managed quests/items/spells, observes player activity through native bridge facts, and drives repeatable reactive content.

## What WM is now

WM is a native-first but external-brain platform.

- Python WM is the reasoning, orchestration, memory, validation, and publish layer
- native AzerothCore modules are the sensing and atomic execution layer
- repo-owned contracts, policies, and manual control remain the safety boundary
- WM is scoped to one explicitly claimed active player at a time for live perception and action

## Current live source policy

Primary live source:
- `native_bridge` through repo-owned `mod-wm-bridge` -> `wm_bridge_event`

Fallback/debug source:
- `combat_log` through `WoWCombatLog.txt`

Legacy path:
- `addon_log` remains in the repo only as a historical/legacy adapter and should not be treated as the primary live path

## Active WM player model

WM should not guess ownership from "who is online" alone.

The authoritative control path is:

1. apply a dedicated WM claim spell / aura to the intended player
2. native bridge emits the spell / aura event
3. WM persists that player's GUID as the active WM scope
4. bridge player scope is updated to that GUID
5. the watcher runs only for that GUID

`characters.online` is still useful as a sanity check, but not as the ownership selector.

## What WM supports today

### Platform

- WM-owned journal, event, cooldown, rollback, and reserved-slot data
- deterministic event spine with inspect, preview, run, and watch flows
- repo-owned bootstrap and bridge-lab workflows
- manual control contract system with dry-run/apply/audit flow

### Native sensing and execution

- `native_bridge` adapter mapping raw bridge rows into canonical WM events
- native bridge action queue with DB-backed policy and player scoping
- native-preferred `quest_grant` through `quest_add`, with SOAP fallback where native is not ready
- typed native action vocabulary under a repo-owned control contract registry

### Managed content

WM has three top-level managed artifact families:

- quests
- items
- spells

The current operator workbench further splits the spell side into practical subtypes:

- managed passive spell-slot drafts
- managed visible spell-slot drafts
- managed item-trigger spell-slot drafts
- WM shell-bank drafts for summon/behavior work

That means the top-level model stays simple, while the workbench stays richer where operators actually need it.

### Event / memory direction

- per-character canonical WM event logging
- per-character subject journal counters and projections
- reactive quest/rule storage
- native context/action groundwork for future richer world-state work

## Quick start

### 1. Install the Python package

```powershell
python -m venv .venv
.venv\\Scripts\\activate
pip install -e .
```

### 2. Copy and edit `.env`

```powershell
Copy-Item .env.example .env
```

At minimum, set DB credentials. Set SOAP credentials only if you want SOAP fallback paths.

### 3. Create the portable workspace

```powershell
.\\setup-wm.bat
```

This creates a repo-relative workspace under `.wm-bootstrap\\`, clones AzerothCore plus the pinned module set, stages local dependencies, and copies repo-owned SQL/addon/helper assets into the workspace.

### 4. Build the core

```powershell
.\\build-wm.bat
```

### 5. Edit the generated realm configs

Main configs after build:

- `.wm-bootstrap\\run\\configs\\worldserver.conf`
- `.wm-bootstrap\\run\\configs\\authserver.conf`
- `.wm-bootstrap\\run\\configs\\modules\\playerbots.conf`
- `.wm-bootstrap\\run\\configs\\modules\\random_enchants.conf`
- `.wm-bootstrap\\run\\configs\\modules\\individualProgression.conf`
- `.wm-bootstrap\\run\\configs\\modules\\mod_weather_vibe.conf`

### 6. Apply WM bootstrap SQL

```powershell
mysql -u root -p acore_world < sql\\bootstrap\\wm_bootstrap.sql
```

## Working live-content flows

### Native bridge perception

Enable observation for one player through native bridge scope:

```powershell
python -m wm.sources.native_bridge.configure --player-guid 5406 --reload-via-soap --summary
```

If SOAP is not enabled, run the same command without `--reload-via-soap`, then execute this in the worldserver console:

```text
.reload config
```

Start the watcher from the current native-bridge high-water mark so old rows do not replay:

```powershell
python -m wm.events.watch --adapter native_bridge --mode apply --player-guid 5406 --confirm-live-apply --summary --print-idle --arm-from-end
```

### Reusable reactive bounty

Install a reusable kill-burst bounty:

```powershell
python -m wm.reactive.install_bounty --player-guid 5406 --subject-entry 6 --quest-id 910000 --turn-in-npc-entry 197 --kill-threshold 4 --window-seconds 120 --post-reward-cooldown-seconds 60 --mode apply --summary
```

Run the watcher against native bridge:

```powershell
python -m wm.events.watch --adapter native_bridge --mode apply --player-guid 5406 --confirm-live-apply --summary --print-idle
```

### Control workbench

Inspect what an event can trigger:

```powershell
python -m wm.control.inspect --event-id 123 --summary
```

Create and dry-run a manual proposal:

```powershell
python -m wm.control.new --event-id 123 --recipe kill_burst_bounty --action quest_grant
python -m wm.control.validate --proposal .wm-bootstrap\\state\\control-proposals\\event-123-kill_burst_bounty-quest_grant.json --summary
python -m wm.control.apply --proposal .wm-bootstrap\\state\\control-proposals\\event-123-kill_burst_bounty-quest_grant.json --mode dry-run --summary
```

Apply still requires explicit live confirmation:

```powershell
python -m wm.control.apply --proposal .wm-bootstrap\\state\\control-proposals\\event-123-kill_burst_bounty-quest_grant.json --mode apply --confirm-live-apply --summary
```

## Native WM development baseline

The rebuilt core lane exists so WM can grow into native modules without giving up the external-first architecture.

For bridge work, use the isolated lab wrappers:

```powershell
.\\setup-bridge-lab.bat
.\\build-bridge-lab.bat
```

For normal native module edits after the first full build:

```powershell
.\\incremental-bridge-lab.bat
.\\stage-bridge-lab-runtime.bat
```

For runtime smoke tests, use the copied lab MySQL data on port `33307` and configure the lab worldserver on non-conflicting ports:

```powershell
.\\start-bridge-lab-mysql.bat
.\\configure-bridge-lab.bat
.\\start-bridge-lab-server.bat
```

## Docs

- [Documentation Index / Start Here](docs/README_OPERATIONS_INDEX.md)
- [WM Platform Handoff](docs/WM_PLATFORM_HANDOFF.md)
- [Work Summary](docs/WORK_SUMMARY.md)
- [Event Watcher Architecture](docs/EVENT_WATCHER_ARCHITECTURE.md)
- [Active WM Player Scope](docs/ACTIVE_WM_PLAYER_SCOPE.md)
- [Native Bridge Action Bus](docs/native-bridge-action-bus.md)
- [Content Workbench V1](docs/CONTENT_WORKBENCH_V1.md)
- [Roadmap](docs/ROADMAP.md)

## Known limitations

- latest-source rebuilt baseline is intentionally not sold as full historical repack parity
- some custom/repack-only content still depends on older SQL/code combinations
- `combat_log` remains fallback/debug only
- `addon_log` remains legacy code in-tree and should not be used as the primary live path
- direct LLM live apply remains intentionally gated behind registered controls and explicit flags
