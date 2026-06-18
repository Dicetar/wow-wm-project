# BridgeLab Operator Environment

Use this profile for live WM operator claims on this workstation:

```powershell
$env:WM_WORLD_DB_PORT = "33307"
$env:WM_CHAR_DB_PORT = "33307"
$env:WM_SOAP_PORT = "7879"

python -m wm.doctor --profile bridgelab --summary
python -m wm.panel serve --live-slice
```

Default `wm.doctor --summary` follows local `WM_*` environment values, which may
target generic local ports (`3306` and `7878`). A live BridgeLab claim should use
`--profile bridgelab` and should report all doctor checks as `WORKING` before
applying proposals.

Current BridgeLab endpoints:

- DB: `127.0.0.1:33307`, user/password `acore` / `acore`
- SOAP: `http://127.0.0.1:7879/`
- Marker spell: `946602`

Generated DBC and client patch artifacts remain local runtime output and are not
committed.
