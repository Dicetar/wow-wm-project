This workspace was staged by WM portable bootstrap.

What lives here:
- `worldserver.conf.dist`, `authserver.conf.dist`, and module `*.conf.dist` will be copied here by `build-wm.bat`
- `.env.example` is the WM-side template for the Python tools
- `../assets/wow_addons/WMBridge` contains the addon-log bridge addon
- `../src/modules/mod-wm-bridge` is the repo-owned native sensor module staged into the workspace during setup
- `../sql/bootstrap` contains WM-owned schema bootstrap SQL
- `../sql/repack` contains repo-owned world overrides
- `../helpers/Test-RuntimeDllGuard.ps1` checks staged runtime DLLs against the build lock

Typical next steps after `build-wm.bat`:
1. Edit `worldserver.conf` and `authserver.conf` with your DB credentials and paths.
2. Apply `sql/bootstrap/wm_bootstrap.sql` to your `acore_world` database.
3. Point `.env` at your DB and live log paths if they differ from the repo-relative defaults.
4. For native bridge testing, keep `WmBridge.PlayerGuidAllowList` empty by default and enable one player with:
   `python -m wm.sources.native_bridge.configure --player-guid 5406 --reload-via-soap --summary`
5. For manual WM control tests, use `python -m wm.control.inspect/new/validate/apply` from the repo root.
