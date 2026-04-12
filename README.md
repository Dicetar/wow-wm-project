# wow-wm-project

World Master for AzerothCore 3.3.5a: an external-first content and reaction platform that can publish quests/items/spells, observe player activity, and drive repeatable reactive content.

## What WM does today

- stores WM-owned journal, event, cooldown, rollback, and reserved-slot data
- generates and publishes managed quests, items, and spells
- runs a deterministic event spine with inspect, preview, run, and watch flows
- grants reusable reactive bounty quests through SOAP
- ingests live kill events through the proven hidden addon-log bridge (`addon_log`)
- includes a native AzerothCore sensor bridge rollout path (`native_bridge`)
- includes a native WM action queue contract for scoped, policy-gated server actions
- includes a WM spell shell bank contract plus native spell behavior runtime (`mod-wm-spells`)
- exposes a repo-owned control contract registry for manual and future LLM-driven actions
- keeps a latest-source AzerothCore baseline available for native WM module work

Current primary live source:
- `addon_log` through `WMBridge` -> AzerothCore addon logging -> `WMOps.log`

Native rollout source:
- `native_bridge` through repo-owned `mod-wm-bridge` -> `wm_bridge_event`
- native actions through `wm_bridge_action_request`, disabled by default and scoped through `wm_bridge_player_scope`

Fallback/debug source:
- `combat_log` through `WoWCombatLog.txt`

## Quick start

### 1. Install the Python package

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### 2. Copy and edit `.env`

```powershell
Copy-Item .env.example .env
```

At minimum, set your DB credentials and SOAP credentials if you want live quest grants.

### 3. Create the portable workspace

```powershell
.\setup-wm.bat
```

This creates a repo-relative workspace under `.wm-bootstrap\`, clones AzerothCore plus the pinned module set, stages local dependencies, and copies repo-owned SQL/addon/helper assets into the workspace.

The setup flow also disables upstream IPP `zz_optional_*.sql` auto-updates by default, so the portable workspace matches the repo policy of no optional IPP SQL extras unless you opt into them manually.

### 4. Build the core

```powershell
.\build-wm.bat
```

This configures and builds AzerothCore from `.wm-bootstrap\src\azerothcore`, then stages a runnable layout under `.wm-bootstrap\run`.

### 5. Edit the generated realm configs

Main configs after build:

- `.wm-bootstrap\run\configs\worldserver.conf`
- `.wm-bootstrap\run\configs\authserver.conf`
- `.wm-bootstrap\run\configs\modules\playerbots.conf`
- `.wm-bootstrap\run\configs\modules\random_enchants.conf`
- `.wm-bootstrap\run\configs\modules\individualProgression.conf`
- `.wm-bootstrap\run\configs\modules\mod_weather_vibe.conf`

### 6. Apply WM bootstrap SQL

```powershell
mysql -u root -p acore_world < sql\bootstrap\wm_bootstrap.sql
```

## Working live-content flows

### Reusable reactive bounty

Install a reusable kill-burst bounty:

```powershell
python -m wm.reactive.install_bounty --player-guid 5406 --subject-entry 6 --quest-id 910000 --turn-in-npc-entry 197 --kill-threshold 4 --window-seconds 120 --post-reward-cooldown-seconds 60 --mode apply --summary
```

Run the watcher against the hidden addon bridge:

```powershell
python -m wm.events.watch --adapter addon_log --mode apply --player-guid 5406 --confirm-live-apply --summary --print-idle
```

### Native bridge rollout

The native module is intentionally inert by default. Enable observation for one player by editing `WmBridge.PlayerGuidAllowList` and reloading config:

```powershell
python -m wm.sources.native_bridge.configure --player-guid 5406 --reload-via-soap --summary
```

If SOAP is not enabled, run the same command without `--reload-via-soap`, then execute this in the worldserver console:

```text
.reload config
```

Start from the current bridge high-water mark so old rows do not replay:

```powershell
python -m wm.events.watch --adapter native_bridge --mode apply --player-guid 5406 --confirm-live-apply --summary --print-idle --arm-from-end
```

Disable native bridge observation live:

```powershell
python -m wm.sources.native_bridge.configure --clear --reload-via-soap --summary
```

Native action bus smoke test after the bridge module is rebuilt in a lab tree:

```powershell
python -m wm.sources.native_bridge.actions_cli scope-player --player-guid 5406 --summary
python -m wm.sources.native_bridge.actions_cli submit --player-guid 5406 --action-kind debug_ping --idempotency-key lab-debug-ping-1 --wait --summary
```

The broad native action vocabulary is already registered in Python/control contracts, but mutation verbs stay disabled and C++ returns `not_implemented` until each verb body is hardened in `D:\WOW\WM_BridgeLab`.

Spell learn / unlearn now also have native queue implementations, and the content workbench prefers them with SOAP fallback. The new summon/ability lane is `shell bank -> mod-wm-spells behavior -> grant shell to player`, not stock spell hijacking.

`quest_grant` now prefers the native bridge `quest_add` path when `mod-wm-bridge` is enabled, the action queue is on, the player is scoped, and the `quest_add` policy is enabled. If native is not ready, WM falls back to the existing SOAP quest path. Override only if needed with `WM_QUEST_GRANT_TRANSPORT=soap` or `WM_QUEST_GRANT_TRANSPORT=native`.

Full action-bus notes and lab commands live in [Native Bridge Action Bus](docs/native-bridge-action-bus.md).

### Control workbench

WM now has a central `control/` registry for events, actions, recipes, policies, examples, generated schemas, and runtime safety checks. Manual proposals use the same schema and coordinator path intended for future LLM proposals.

Inspect what an event can trigger:

```powershell
python -m wm.control.inspect --event-id 123 --summary
```

Create and dry-run a manual proposal:

```powershell
python -m wm.control.new --event-id 123 --recipe kill_burst_bounty --action quest_grant
python -m wm.control.validate --proposal .wm-bootstrap\state\control-proposals\event-123-kill_burst_bounty-quest_grant.json --summary
python -m wm.control.apply --proposal .wm-bootstrap\state\control-proposals\event-123-kill_burst_bounty-quest_grant.json --mode dry-run --summary
```

Apply still requires an explicit live confirmation:

```powershell
python -m wm.control.apply --proposal .wm-bootstrap\state\control-proposals\event-123-kill_burst_bounty-quest_grant.json --mode apply --confirm-live-apply --summary
```

LLM-authored proposals are additionally blocked unless `WM_LLM_DIRECT_APPLY=1` is set. Manual proposals do not need that flag, but they still pass schema, policy, idempotency, source-event, player-scope, and dry-run gates.

Common manual shortcuts only build proposal JSON; they do not bypass the coordinator:

```powershell
python -m wm.control.manual_grant_quest --event-id 123 --player-guid 5406 --quest-id 910000
python -m wm.control.manual_announce --player-guid 5406 --text "WM test" --manual-reason "local smoke test"
python -m wm.control.manual_noop --player-guid 5406 --reason "observe only" --manual-reason "local smoke test"
```

### Native WM development baseline

The rebuilt core lane exists so WM can grow into a native module later without giving up the current external-first architecture.

Important current truth:

- it is suitable for native WM module development
- it is not yet guaranteed gameplay parity with the old repack
- some repack-specific custom NPC/world behavior still drifts from the historical setup
- WeatherVibe still needs real in-world profile content, but the lab configurator now forces `WeatherVibe.Debug = 0` so debug spam stays off by default

For bridge work, use the isolated lab wrappers instead of touching the working rebuild:

```powershell
.\setup-bridge-lab.bat
.\build-bridge-lab.bat
```

For day-to-day lab runtime use, the repo also includes:

```powershell
.\start-bridge-lab-server.bat
```

This starts lab MySQL, syncs the auth realmlist to the lab world port, and gives you a menu with a graceful-first worldserver restart path.

After the first full lab build, use the incremental path for normal native module edits:

```powershell
.\incremental-bridge-lab.bat
.\stage-bridge-lab-runtime.bat
```

For runtime smoke tests, use the copied lab MySQL data on port `33307` and configure the lab worldserver on non-conflicting ports:

```powershell
.\start-bridge-lab-mysql.bat
.\configure-bridge-lab.bat
```

This points only the lab configs at the lab MySQL copy. `configure-bridge-lab.bat` also forces `mod_weather_vibe.conf` to `WeatherVibe.Debug = 0`. The working rebuild remains on its own MySQL/runtime tree. Promotion back to the working rebuild is intentionally gated by `scripts\bridge_lab\Promote-BridgeBuild.ps1 -ConfirmPromoteToWorkingRebuild`.

If you use Questie-335 while testing WM custom quests like `910000`, copy `wow_addons\WMQuestieCompat` into your client `Interface\AddOns\` folder and `/reload`. It suppresses Questie tracker spam for WM-owned quest ids that do not exist in the upstream Questie database.

## Repo layout

- `bootstrap/`
  - portable source/dependency lockfile and workspace templates
- `scripts/bootstrap/`
  - repo-relative `setup` and `build` flow
- `scripts/repack/`
  - older/latest-baseline rebuild helpers and compatibility tools
- `scripts/bridge_lab/`
  - isolated native bridge setup/build/incremental/runtime/promotion helpers
- `sql/bootstrap/`
  - WM-owned schema bootstrap SQL
- `control/`
  - WM event/action/recipe/policy contracts for manual and future LLM tools
- `sql/repack/`
  - repo-owned world/repack compatibility overrides
- `wow_addons/WMBridge/`
  - hidden addon bridge source
- `src/wm/`
  - WM codebase

## Docs

- [Work Summary](docs/WORK_SUMMARY.md)
- [Summon and Spell Platform Status](docs/SUMMON_SPELL_PLATFORM_STATUS.md)
- [Native Bridge Action Bus](docs/native-bridge-action-bus.md)
- [Content Workbench V1](docs/CONTENT_WORKBENCH_V1.md)
- [On-The-Fly Spells V1](docs/ON_THE_FLY_SPELLS_V1.md)
- [Portable Rebuild Notes](docs/repack-rebuild.md)
- [Roadmap](docs/ROADMAP.md)
- archived bootstrap-era docs remain under `docs/archive/`

## Known limitations

- rebuilt latest-source baseline is intentionally not sold as byte-for-byte repack parity
- some custom/repack-only content still depends on older SQL/code combinations
- `combat_log` remains fallback/debug only
- optional IPP extras are intentionally excluded from the default portable bootstrap path
- direct LLM live apply is intentionally gated behind `WM_LLM_DIRECT_APPLY=1` and registered controls only
