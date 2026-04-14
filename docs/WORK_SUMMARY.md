Status: PARTIAL
Last verified: 2026-04-14
Verified by: ChatGPT
Doc type: handoff

# Work Summary

For the best current entrypoint, start with:

- [Documentation Index](README_OPERATIONS_INDEX.md)
- [WM Platform Handoff](WM_PLATFORM_HANDOFF.md)

This repository is now a real WM platform baseline, not just an idea pile.

## What was built

### Event spine

- canonical WM event log, cursor storage, cooldowns, and reaction history
- inspect, preview, run, and watch flows
- deterministic planning and execution against the existing publish pipeline

### Reactive quest pipeline

- reusable reactive bounty rule storage
- direct quest grant through SOAP and native-preferred `quest_add`
- runtime quest-state polling from the characters DB
- suppression while a reactive quest is active, complete-but-not-turned-in, or cooling down after reward

### Legacy addon bridge

- `WMBridge` addon under `wow_addons/WMBridge`
- hidden addon-message transport
- addon-log adapter and tailer code still exist in-tree as a legacy path
- this should not be treated as the primary live source going forward

### Native bridge path

- repo-owned `mod-wm-bridge` native module
- append-only `wm_bridge_event` raw event table
- `native_bridge` WM adapter maps raw rows into canonical events
- DB-backed player scope through `wm_bridge_player_scope`
- native action bus foundation through `wm_bridge_action_request`, `wm_bridge_action_policy`, and `wm_bridge_runtime_status`
- broad native action vocabulary is registered, with `debug_ping`, `debug_echo`, `debug_fail`, `context_snapshot_request`, `world_announce_to_player`, and `quest_add` proven in the first safe slice
- successful native `quest_add` emits a native `quest/granted` bridge event so perception stays aligned with mutation
- `quest_grant` remains the public WM action, but now prefers native bridge when the player/policy/config path is ready and falls back to SOAP otherwise
- `combat_log` remains retained only as fallback/debug

### Control contract workbench

- repo-owned `control/` registry for events, actions, recipes, policies, examples, schemas, and runtime checks
- `native_bridge_action` contract lets humans and later LLMs submit one fixed native action kind through the same proposal gates
- manual inspect/new/validate/apply commands exercise the same coordinator path as LLM proposals
- live apply is one registered action per proposal, with player scope, source event checks, dry-run, idempotency, and audit state
- LLM-authored live apply is blocked unless `WM_LLM_DIRECT_APPLY=1`

### Shared internal refs and journaling base

- typed refs for players, creatures, NPCs, quests, items, and spells
- internal schemas now carry structured refs instead of leaking anonymous integers everywhere
- per-character subject-journal projection exists as the current memory baseline
- richer daily rollups, world-pressure logic, and explicit active-player claim state are the next architectural layer, not yet the current baseline

### Rebuilt latest-source baseline

- latest Playerbot-branch AzerothCore source reconstruction
- large module set cloned from upstream/community repos
- compatibility overlay for loader/API drift
- launcher/rebuild helpers for native WM module work
- repo-owned lab launcher and realmlist sync helpers for `D:\WOW\WM_BridgeLab`
- isolated bridge lab wrappers keep native rebuild experiments in `D:\WOW\WM_BridgeLab` instead of the working rebuild
- incremental bridge lab build/stage wrappers avoid full rebuilds after the first generated solution exists
- isolated lab MySQL can run from the copied lab data directory on port `33307`, keeping bridge queue tests off the working DB

### Managed content lane

The platform-level managed artifact families are:

- quests
- items
- spells

The current operator-facing content workbench further splits the spell/content lane into:

- managed items
- managed passive spell-slot drafts
- managed visible spell-slot drafts
- managed item-trigger spell-slot drafts
- WM shell-bank drafts for summon/behavior work

This is intentional. The platform model stays simple while the operator workbench stays rich.

## Current source of truth

For the portable workflow, the repo now owns:

- WM SQL bootstrap and overrides
- WM control contracts and proposal examples
- native bridge module and runtime docs
- portable source/dependency manifest
- bootstrap/build scripts
- docs for setup and development

## Known limitations

- latest-source rebuilt realm is good for WM/native module development, but not guaranteed gameplay parity with the old repack
- some repack-specific/custom NPC or world content still drifts because newer module trees do not perfectly match the historical pack
- WeatherVibe is loaded but still needs meaningful zone/profile data
- optional IPP extras are intentionally excluded from the default portable bootstrap path
- most native mutation action kinds are intentionally disabled/not implemented until their C++ bodies pass lab tests
- active WM player claiming through a dedicated aura/scope flow is the intended control model, but should still be treated as design-target architecture until it is wired end-to-end
- Questie needs a tiny compat shim for WM custom quest ids because upstream Questie-335 does not know repo-owned quest ids like `910000`

## Recommended workflow

1. clone repo
2. run `setup-wm.bat`
3. run `build-wm.bat`
4. edit `.wm-bootstrap\\run\\configs\\worldserver.conf` and `.wm-bootstrap\\run\\configs\\authserver.conf`
5. apply `sql\\bootstrap\\wm_bootstrap.sql`
6. use `python -m wm.sources.native_bridge.configure`, `wm.events.watch --adapter native_bridge`, and `wm.control.inspect/new/validate/apply` for live/manual tests
7. continue WM feature work from the repo, not from machine-local rebuild leftovers

For native bridge action work, use `setup-bridge-lab.bat` and `build-bridge-lab.bat` once, then use `incremental-bridge-lab.bat` for normal C++ edits. Runtime tests should start `start-bridge-lab-mysql.bat`, run `configure-bridge-lab.bat`, and prove `debug_ping`/`debug_echo`/`debug_fail` before promoting anything back to a working realm.
