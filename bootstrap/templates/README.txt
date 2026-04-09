This workspace was staged by WM portable bootstrap.

What lives here:
- `worldserver.conf.dist`, `authserver.conf.dist`, and module `*.conf.dist` will be copied here by `build-wm.bat`
- `.env.example` is the WM-side template for the Python tools
- `../assets/wow_addons/WMBridge` contains the addon-log bridge addon
- `../sql/bootstrap` contains WM-owned schema bootstrap SQL
- `../sql/repack` contains repo-owned world overrides

Typical next steps after `build-wm.bat`:
1. Edit `worldserver.conf` and `authserver.conf` with your DB credentials and paths.
2. Apply `sql/bootstrap/wm_bootstrap.sql` to your `acore_world` database.
3. Point `.env` at your DB and live log paths if they differ from the repo-relative defaults.
