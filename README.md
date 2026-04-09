# wow-wm-project

World Master for AzerothCore 3.3.5a: an external-first content and reaction platform that can publish quests/items/spells, observe player activity, and drive repeatable reactive content.

## What WM does today

- stores WM-owned journal, event, cooldown, rollback, and reserved-slot data
- generates and publishes managed quests, items, and spells
- runs a deterministic event spine with inspect, preview, run, and watch flows
- grants reusable reactive bounty quests through SOAP
- ingests live kill events primarily through the hidden addon-log bridge (`addon_log`)
- keeps a latest-source AzerothCore baseline available for native WM module work

Current primary live source:
- `addon_log` through `WMBridge` -> AzerothCore addon logging -> `WMOps.log`

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

### Native WM development baseline

The rebuilt core lane exists so WM can grow into a native module later without giving up the current external-first architecture.

Important current truth:

- it is suitable for native WM module development
- it is not yet guaranteed gameplay parity with the old repack
- some repack-specific custom NPC/world behavior still drifts from the historical setup
- WeatherVibe still needs real in-world profile content

## Repo layout

- `bootstrap/`
  - portable source/dependency lockfile and workspace templates
- `scripts/bootstrap/`
  - repo-relative `setup` and `build` flow
- `scripts/repack/`
  - older/latest-baseline rebuild helpers and compatibility tools
- `sql/bootstrap/`
  - WM-owned schema bootstrap SQL
- `sql/repack/`
  - repo-owned world/repack compatibility overrides
- `wow_addons/WMBridge/`
  - hidden addon bridge source
- `src/wm/`
  - WM codebase

## Docs

- [Work Summary](docs/WORK_SUMMARY.md)
- [Portable Rebuild Notes](docs/repack-rebuild.md)
- [Roadmap](docs/ROADMAP.md)
- archived bootstrap-era docs remain under `docs/archive/`

## Known limitations

- rebuilt latest-source baseline is intentionally not sold as byte-for-byte repack parity
- some custom/repack-only content still depends on older SQL/code combinations
- `combat_log` remains fallback/debug only
- optional IPP extras are intentionally excluded from the default portable bootstrap path
