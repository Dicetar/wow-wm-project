# Portable Bootstrap and Build

The repo now supports a portable, repo-relative bootstrap path for native WM development.

This is the default workflow:

1. clone repo
2. run `setup-wm.bat`
3. run `build-wm.bat`

The goal is not byte-for-byte repack recovery. The goal is a current, buildable AzerothCore + module workspace that WM can keep using and extending.

## What setup does

`setup-wm.bat` calls `scripts/bootstrap/Setup-Workspace.ps1`.

It creates a workspace under `.wm-bootstrap\` and then:

- clones the Playerbot AzerothCore core
- clones the pinned module set from `bootstrap/sources.lock.json`
- creates module junctions inside `.wm-bootstrap\src\azerothcore\modules`
- downloads and stages local build dependencies under `.wm-bootstrap\deps`
- copies repo-owned SQL, client compatibility, and helper assets into `.wm-bootstrap\run`
- records setup state under `.wm-bootstrap\state`

Default workspace layout:

- `.wm-bootstrap\src\azerothcore`
- `.wm-bootstrap\src\modules`
- `.wm-bootstrap\deps`
- `.wm-bootstrap\downloads`
- `.wm-bootstrap\build`
- `.wm-bootstrap\run`
- `.wm-bootstrap\state`
- `.wm-bootstrap\logs`

## What build does

`build-wm.bat` calls `scripts/bootstrap/Build-Workspace.ps1`.

It then:

- applies repo-owned SQL overrides into the cloned AzerothCore tree
- applies the compatibility overlay for known module drift
- configures CMake against `.wm-bootstrap\src\azerothcore`
- builds into `.wm-bootstrap\build`
- stages runtime DLLs and config templates
- records a runtime DLL lock under `.wm-bootstrap\state\runtime-dlls.lock.json`
- copies a runnable layout into `.wm-bootstrap\run`

Primary outputs after build:

- `.wm-bootstrap\run\bin`
- `.wm-bootstrap\run\configs`
- `.wm-bootstrap\run\logs`
- `.wm-bootstrap\state\runtime-dlls.lock.json`

The runtime DLL lock records hashes for `libmysql.dll`, `libcrypto-3-x64.dll`, `libssl-3-x64.dll`, and `legacy.dll`. The rebuilt launcher runs the guard when the helper exists, so mixed OpenSSL/MySQL DLLs fail before the server opens mystery Windows entry-point dialogs.

## Bridge lab lane

Native bridge work should use the isolated lab, not the working rebuild:

```powershell
.\setup-bridge-lab.bat
.\build-bridge-lab.bat
```

After that first full configure/build, use the incremental path:

```powershell
.\incremental-bridge-lab.bat
```

Useful lab runtime helpers:

- `start-bridge-lab-mysql.bat` starts the copied lab MySQL data tree on port `33307`.
- `configure-bridge-lab.bat` points lab configs at port `33307`, sets lab world port `8095`, sets lab SOAP port `7879`, and enables DB-controlled bridge scope/action queue.
- `stage-bridge-lab-runtime.bat` restages successful build outputs and rewrites the runtime DLL lock.
- `stop-bridge-lab-mysql.bat` stops only the lab MySQL process.

The lab lane is for destructive/repeatable native bridge testing. Promotion back to the working rebuild is gated separately by `scripts\bridge_lab\Promote-BridgeBuild.ps1 -ConfirmPromoteToWorkingRebuild`.

## Source of truth

The canonical bootstrap manifest is:

- `bootstrap/sources.lock.json`

That lockfile owns:

- core repo and branch
- module repo list
- dependency download sources
- workspace tree expectations
- staged repo assets
- repo-owned SQL override paths

## Main tweak points after build

- `.wm-bootstrap\run\configs\worldserver.conf`
- `.wm-bootstrap\run\configs\authserver.conf`
- `.wm-bootstrap\run\configs\modules\playerbots.conf`
- `.wm-bootstrap\run\configs\modules\random_enchants.conf`
- `.wm-bootstrap\run\configs\modules\individualProgression.conf`
- `.wm-bootstrap\run\configs\modules\mod_weather_vibe.conf`

WM-side environment template:

- `.env.example`

## What is intentionally excluded

The default portable path intentionally does **not** depend on:

- your old repack tree
- your current rebuilt tree
- your current WoW client path
- raw MySQL datadir backups
- optional IPP extras

This path is for:

- source checkout
- dependency staging
- core build
- WM development readiness

It is not a full DB import/migration lane and it is not a promise of gameplay parity with the historical repack.

## Related repo assets

- WM bootstrap SQL: `sql/bootstrap`
- WM control registry: `control`
- repack/world overrides: `sql/repack`
- retired client-message prototype source: `wow_addons/WMBridge`
- runtime DLL guard: `scripts/bootstrap/Test-RuntimeDllGuard.ps1`
- compatibility overlay: `scripts/repack/Apply-RepackCompatibilityOverlay.ps1`
- work summary: `docs/WORK_SUMMARY.md`
