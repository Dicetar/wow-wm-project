# Build A Current WM Source Tree

This workflow now targets a **latest working baseline**, not byte-for-byte repack recovery.

The goal is practical:

- get a full AzerothCore + modules source tree
- keep your current DBs in place
- build a working `authserver` / `worldserver`
- use that tree to continue native WM module development

## Current baseline

- Core family: `mod-playerbots/azerothcore-wotlk`
- Branch: `Playerbot`
- Default strategy: use the **latest branch head**
- Live repack revision is kept only as a reference point
- DBs kept in place:
  - `acore_auth`
  - `acore_world`
  - `acore_characters`
  - `acore_playerbots`

Why this changed:

- exact repack parity is not realistic from the currently available artifacts
- current upstream heads are easier to build and maintain
- WM needs a working native build tree more than it needs historical reconstruction

## What the tooling does

- `python -m wm.repack.discovery`
  - exports a live manifest from the current repack root, DB update tables, config overlays, logs, and optional SQL
- `scripts/repack/New-ExactSourceTree.ps1`
  - creates a new source/build/run workspace side-by-side
  - clones the current Playerbot core branch
  - clones the repack module set from the module catalog
  - can build in-place with `-Build`
- `scripts/repack/Resolve-ModuleRepos.ps1`
  - probes repo mappings and reports which non-pinned candidates are reachable
- `scripts/repack/Audit-UpgradeDrift.ps1`
  - compares your current config overlays against fresh upstream config templates

Generated files:

- `data/repack/live-repack-manifest.json`
- `data/repack/live-repack-source-gaps.md`
- `data/repack/module-repo-resolution.md`
- `data/repack/upgrade-drift-report.md`

## Recommended workflow

1. Back up the portable MySQL data directories under the repack before first switch-over.

2. Export the current live manifest:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\repack\Export-LiveManifest.ps1
   ```

3. Review the manifest outputs:

   - `data/repack/live-repack-manifest.json`
   - `data/repack/live-repack-source-gaps.md`

4. Build the side-by-side workspace:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\repack\New-ExactSourceTree.ps1
   ```

5. Build the reconstructed tree:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\repack\New-ExactSourceTree.ps1 -Build -BuildOnly
   ```

6. If you explicitly want to try the historical live commit instead of the latest Playerbot branch head:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\repack\New-ExactSourceTree.ps1 -PinLiveCore
   ```

## Important behavior

- The default bootstrap now prefers the **latest Playerbot branch head**.
- The live repack hash is treated as diagnostic/reference information.
- Module repo URLs provided directly by you are treated as trusted source mappings.
- Some community modules may still need compatibility overlays for loader names or API drift.
- Optional SQL under `optional\` is still staged for review only.

## What this rebuilt tree is for

Treat the rebuilt tree as a **native WM development baseline**, not as a parity-certified drop-in replacement for the old repack.

Today it is good for:

- building `authserver` / `worldserver`
- keeping all major module sources in one place
- continuing WM native-module work against a modern buildable tree

Today it is **not yet** good for claiming gameplay parity. Known limitations from live validation:

- Individual Progression is currently not trustworthy; the DB still references `npc_ipp_*` / `gobject_ipp_*` scripts that the rebuilt source set does not currently provide
- some old service NPCs or custom spawns may be missing or partially mismatched because older SQL/update streams do not line up cleanly with current upstream module trees
- WeatherVibe loads, but it is not yet meaningfully configured in-world

## Launch and rebuild helpers

Repo-side helpers:

- `scripts/repack/Start-Rebuilt-Server.bat`
- `scripts/repack/Rebuild-Rebuilt-Server.bat`

In the current Windows workflow, copies of those helpers can also be placed in the rebuilt root so you can launch or rebuild from there directly.

Typical loop:

1. edit source or module code
2. run `Rebuild-Rebuilt-Server.bat`
3. run `Start-Rebuilt-Server.bat`

If you only changed configs, rebuild is not needed; restart is enough.

## Config locations

Within the rebuilt run tree:

- main configs: `run/configs/`
- module configs: `run/configs/modules/`

Common tweak points:

- `run/configs/worldserver.conf`
- `run/configs/authserver.conf`
- `run/configs/modules/playerbots.conf`
- `run/configs/modules/random_enchants.conf`
- `run/configs/modules/individualProgression.conf`
- `run/configs/modules/mod_weather_vibe.conf`

## Runtime safety rules

- Do not run old and rebuilt `worldserver.exe` / `authserver.exe` against the same DBs at the same time.
- First parity boot should happen only with the old server stopped.
- No dump/import is required for this lane; the rebuilt server is expected to reuse the current portable MySQL data.

## Config drift lane

After the source tree is building, use the audit lane to surface new settings:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\repack\Audit-UpgradeDrift.ps1
```

When that report shows new or changed config options, resolve them in one batch before switching the rebuilt server into normal use.
