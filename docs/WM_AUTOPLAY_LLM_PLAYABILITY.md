Status: PARTIAL
Last verified: 2026-05-25
Verified by: Codex
Doc type: howto / status

# WM Autoplay + LLM Playability

Autoplay is the local no-Codex runtime loop for playing with WM active. It does
not give the LLM direct mutation powers. The LLM can only return typed drafts
from the existing schema catalog; WM then validates, dry-runs, policy-checks,
applies through owned gates, audits, and parks issues or maintenance.

## Run

BridgeLab operator profile:

```powershell
.\start-wm-playable.bat --player-guid 5408
```

Status and stop:

```powershell
.\status-wm-playable.bat
.\stop-wm-playable.bat
```

Direct Python commands:

```powershell
$env:WM_WORLD_DB_PORT = "33307"
$env:WM_CHAR_DB_PORT = "33307"
$env:WM_SOAP_PORT = "7879"
$env:WM_SOAP_ENABLED = "1"

python -m wm.autoplay run --player-guid 5408
python -m wm.autoplay status --summary
python -m wm.autoplay pause --summary
python -m wm.autoplay resume --summary
python -m wm.autoplay stop --summary
```

For a non-mutating status tick:

```powershell
python -m wm.autoplay run --once --no-start-watcher --player-guid 5408 --summary
```

## Current Behavior

- Durable state lives under `.wm-bootstrap/state/autoplay`.
- Panel status is exposed at `GET /api/wm/autoplay/status`.
- Panel pause/resume controls call `POST /api/wm/autoplay/pause` and
  `POST /api/wm/autoplay/resume`.
- `python -m wm.context.pack build --player-guid <guid>` writes a session-level
  context pack; target/event-specific packs still delegate to `wm.context.builder`.
- The schema-driven LLM adapter supports the current playable schema set:
  quests, managed items, shell abilities, native scenes, and control proposals.
- The autoplay policy defaults to `low` risk, requires green readiness, a
  configured LM Studio model, an active session, successful dry-run, fresh source
  event, unused idempotency, rollback where required, and lane budget.
- DBC-backed spell/shell proposals are staged as maintenance when the WoW client
  is running or the scoped player is active.
- When an in-process WM session runtime is available, autoplay dry-runs pending
  gate proposals without consuming them, then applies only policy-eligible items.

## Known Gaps

- This is the autoplay foundation and approval-gate driver. A full live
  all-lane proof still needs BridgeLab gameplay acceptance with the player
  online and real LM Studio responses.
- The service starts the existing auto-bounty watcher, but all-lane opportunity
  discovery should be widened incrementally from proven event patterns.
- DBC maintenance is staged and visible; automatic safe-window restart/client
  patch execution should stay conservative until the live shell rollback proof is
  complete.
