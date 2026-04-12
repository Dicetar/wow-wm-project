# Work Summary

This repository is now a real WM platform baseline, not just an idea pile.

## What was built

### Event spine

- canonical WM event log, cursor storage, cooldowns, and reaction history
- inspect, preview, run, and watch flows
- deterministic planning and execution against the existing publish pipeline

### Reactive quest pipeline

- reusable reactive bounty rule storage
- direct quest grant through SOAP
- runtime quest-state polling from the characters DB
- suppression while a reactive quest is active, complete-but-not-turned-in, or cooling down after reward

### Hidden addon bridge

- `WMBridge` addon under `wow_addons/WMBridge`
- hidden addon-message transport
- addon-log adapter reading AzerothCore addon-message logging as the current working live source
- `combat_log` retained only as fallback/debug

### Native bridge rollout

- repo-owned `mod-wm-bridge` native module
- append-only `wm_bridge_event` raw event table
- `native_bridge` WM adapter maps raw rows into canonical events
- module is inert by default through empty `WmBridge.PlayerGuidAllowList`
- WM helper can update the allowlist and reload config without a worldserver restart
- DB-backed player scope through `wm_bridge_player_scope` can be enabled for live allowlist control after bootstrap SQL is present
- native action bus foundation through `wm_bridge_action_request`, `wm_bridge_action_policy`, and `wm_bridge_runtime_status`
- broad native action vocabulary is registered, with `debug_ping`, `debug_echo`, `debug_fail`, `context_snapshot_request`, `world_announce_to_player`, and `quest_add` proven in the first safe slice
- successful native `quest_add` now emits a native `quest/granted` bridge event so perception stays aligned with mutation
- `quest_grant` remains the public WM action, but now prefers native bridge when the player/policy/config path is ready and falls back to SOAP otherwise

### Control contract workbench

- repo-owned `control/` registry for events, actions, recipes, policies, examples, schemas, and runtime checks
- `native_bridge_action` contract lets humans and later LLMs submit one fixed native action kind through the same proposal gates
- Pydantic `ControlProposal` contract is shared by manual proposals and future LLM proposals
- manual inspect/new/validate/apply commands exercise the same coordinator path as LLM proposals
- live apply is one registered action per proposal, with player scope, source event checks, dry-run, idempotency, and audit state
- LLM-authored live apply is blocked unless `WM_LLM_DIRECT_APPLY=1`

### Runtime DLL guard

- build now records a `runtime-dlls.lock.json` hash inventory for MySQL/OpenSSL runtime DLLs
- rebuilt launcher can fail fast before `authserver.exe` or `worldserver.exe` starts with mismatched DLLs
- this directly targets the previous `legacy.dll` / `libcrypto` entry-point breakage

### Shared internal refs

- typed refs for players, creatures, NPCs, quests, items, and spells
- internal schemas now carry structured refs instead of leaking anonymous integers everywhere

### Rebuilt latest-source baseline

- latest Playerbot-branch AzerothCore source reconstruction
- large module set cloned from upstream/community repos
- compatibility overlay for loader/API drift
- launcher/rebuild helpers for native WM module work
- repo-owned lab launcher and realmlist sync helpers for `D:\WOW\WM_BridgeLab`
- isolated bridge lab wrappers keep native rebuild experiments in `D:\WOW\WM_BridgeLab` instead of the working rebuild
- incremental bridge lab build/stage wrappers avoid full rebuilds after the first generated solution exists
- isolated lab MySQL can run from the copied lab data directory on port `33307`, keeping bridge queue tests off the working DB
- graceful-first lab worldserver restart helper falls back to force only if the process hangs
- bridge lab runtime configuration forces `WeatherVibe.Debug = 0` so weather debugging does not spam the client during WM tests
- summon/spell platform status is documented separately in `docs/SUMMON_SPELL_PLATFORM_STATUS.md`, including retired stock-carrier paths and the current shell-bank direction

### IPP cleanup work

- normalized the realm/client to `patch-S`
- kept the three required `Skill*.dbc` files active
- rolled back IPP optional SQL changes from the live world DB
- preserved mailbox unphasing through a repo-owned override SQL

## Current source of truth

For the portable workflow, the repo now owns:

- WM SQL bootstrap and overrides
- WM control contracts and proposal examples
- addon bridge source
- portable source/dependency manifest
- bootstrap/build scripts
- docs for setup and development

## Known limitations

- latest-source rebuilt realm is good for WM/native module development, but not guaranteed gameplay parity with the old repack
- some repack-specific/custom NPC or world content still drifts because newer module trees do not perfectly match the historical pack
- WeatherVibe is loaded but still needs meaningful zone/profile data
- optional IPP extras are intentionally excluded from the default portable bootstrap path
- most native mutation action kinds are intentionally disabled/not implemented until their C++ bodies pass lab tests
- Questie needs a tiny compat shim for WM custom quest ids because upstream Questie-335 does not know repo-owned quest ids like `910000`

## Recommended workflow

1. clone repo
2. run `setup-wm.bat`
3. run `build-wm.bat`
4. edit `.wm-bootstrap\run\configs\worldserver.conf` and `.wm-bootstrap\run\configs\authserver.conf`
5. apply `sql\bootstrap\wm_bootstrap.sql`
6. use `python -m wm.control.inspect/new/validate/apply` for manual control tests
7. continue WM feature work from the repo, not from machine-local rebuild leftovers

For native bridge action work, use `setup-bridge-lab.bat` and `build-bridge-lab.bat` once, then use `incremental-bridge-lab.bat` for normal C++ edits. Runtime tests should start `start-bridge-lab-mysql.bat`, run `configure-bridge-lab.bat`, and prove `debug_ping`/`debug_echo`/`debug_fail` before promoting anything back to a working realm.
