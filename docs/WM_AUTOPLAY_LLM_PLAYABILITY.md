Status: PARTIAL
Last verified: 2026-05-26
Verified by: Codex
Doc type: howto / status

# WM Autoplay + LLM Playability

Autoplay is the local no-Codex runtime loop for playing with WM active. It does
not give the LLM direct mutation powers. The LLM can only return typed drafts
from the existing schema catalog; WM then validates, dry-runs, policy-checks,
applies through owned gates, audits, and parks issues or maintenance.

## Run

Preferred visible launcher:

```powershell
.\start-wm-launcher.bat --player-guid 5408
python -m wm.launcher --player-guid 5408
```

The launcher opens one Windows control app. Its long-running runtime buttons
start visible console windows for BridgeLab MySQL, authserver, worldserver,
the native watcher, autoplay, and the panel server. Use this path for normal
playability testing so stuck services are visible.

Legacy BridgeLab operator profile:

```powershell
.\start-wm-playable.bat --player-guid 5408
.\start-wm-playable.bat -PlayerGuid 5408 -LlmModel mistralai/mistral-nemo-instruct-2407
```

Status and stop:

```powershell
.\status-wm-playable.bat
.\stop-wm-playable.bat
.\start-wm-panel-app.bat
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

LLM controls:

```powershell
python -m wm.autoplay configure --llm-enabled --llm-lanes scene,action --llm-model mistral-nemo-instruct-2407 --summary
python -m wm.autoplay configure --llm-disabled --summary
python -m wm.autoplay generate --player-guid 5408 --lane scene --summary
python -m wm.autoplay chat --player-guid 5408 --llm-model mistralai/mistral-nemo-instruct-2407 --message "What should I do next?" --summary
```

In-game direct WM chat:

```text
/join WM
<type normally in the WM channel>
/wm What should I do next?
towm What should I do next?
```

`start-wm-playable.bat` starts both the native BridgeLab watcher and an
`addon_log` watcher. The preferred input is the custom chat channel named `WM`:
join it and type normally in that channel. The native bridge records those lines
as `wm_chat` events, and the addon mirrors the same channel as a fallback. The
addon also provides `/wm <message>`, which sends a real channel message to `WM`.
Plain `towm <message>` remains as a prefix fallback in Say, Party, Guild,
Whisper, or other channels.

Autoplay replies through the native `player_chat_message` action. Its default
style is a chat-box channel line on `WM` from `WorldMaster`, with `whisper` and
`system` styles available for tests. The player must be online and scoped by the
native bridge.

For a non-mutating status tick:

```powershell
python -m wm.autoplay run --once --no-start-watcher --player-guid 5408 --summary
```

`start-wm-playable.bat` is a legacy background helper. It launches the autoplay
service in the background and then returns to PowerShell. Logs are written to
`.wm-bootstrap/state/autoplay/autoplay.stdout.log` and
`.wm-bootstrap/state/autoplay/autoplay.stderr.log`.

The batch helper defaults to `chat` lane only. This prevents LM Studio from
continuously drafting reactions to ordinary movement/aura/native events while
you are only testing in-game WM chat. To enable autonomous scene/action drafting
later, pass `-LlmLanes scene,action` intentionally.

## Current Behavior

- Durable state lives under `.wm-bootstrap/state/autoplay`.
- Panel status is exposed at `GET /api/wm/autoplay/status`.
- Panel pause/resume controls call `POST /api/wm/autoplay/pause` and
  `POST /api/wm/autoplay/resume`.
- Panel LLM controls call `POST /api/wm/autoplay/configure`.
- Panel one-shot generation calls `POST /api/wm/autoplay/generate`.
- Panel tool visibility is exposed at `GET /api/wm/tools`.
- `start-wm-panel-app.bat` opens the local panel in a separate Edge/Chrome app
  window. The panel has Simple mode for play/publish/LLM controls and Advanced
  mode for the full existing operator surface.
- `python -m wm.context.pack build --player-guid <guid>` writes a session-level
  context pack; target/event-specific packs still delegate to `wm.context.builder`.
- The schema-driven LLM adapter supports the current playable schema set:
  quests, managed items, managed spells, shell abilities, native scenes, and
  control proposals.
- The service loop now scans fresh observed events for the active player and
  generates one typed draft per eligible event/cooldown window. Generated drafts
  are saved under `.wm-bootstrap/state/autoplay/drafts` and mirrored into the
  panel draft store.
- Deterministic code locks player GUID, source event, stable keys, reserved draft
  IDs, native action scope, author kind, and low-risk control/action metadata
  after the model responds.
- The autoplay policy defaults to `low` risk, requires green readiness, a
  configured LM Studio model, an active session, successful dry-run, fresh source
  event, unused idempotency, rollback where required, and lane budget.
- DBC-backed spell/shell proposals are staged as maintenance when the WoW client
  is running or the scoped player is active.
- When an in-process WM session runtime is available, autoplay dry-runs pending
  gate proposals without consuming them, then applies only policy-eligible items.
- Validated `scene` and `action` LLM drafts are now compiled into deterministic
  manual-admin control proposals, dry-run through the live control coordinator,
  policy-checked, applied with `confirm_live_apply`, and recorded back into the
  durable autoplay queue. The original LLM draft/source event stays in metadata
  for audit.
- Validated `quest`, `item`, and `spell` drafts now compile into existing
  `ReactionPlan` publisher actions. Quest drafts can publish a managed repeatable
  bounty and direct-grant it through the configured quest transport. Item drafts
  route through `item_publish`. Spell drafts route through `spell_publish` and
  remain subject to DBC safe-window policy.
- `python -m wm.autoplay chat` asks the configured local model for a concise WM
  reply and sends it through `player_chat_message`; the player must be online
  and scoped by the native bridge.
- Real in-game chat lines in the `WM` custom channel, plus `towm ` fallback
  lines, use the same reply path. They start from native/addon observed
  `wm_chat` events. Direct chat events bypass the normal content-draft cooldown
  so explicit player questions are answered immediately when readiness and LM
  Studio are green.

## Known Gaps

- This is the autoplay foundation and approval-gate driver. A full live
  all-lane proof still needs BridgeLab gameplay acceptance with the player
  online and real LM Studio responses.
- Event-to-draft generation and automatic event-to-apply are wired for action,
  scene, quest, item, and spell drafts. Shell/ability drafts still stage as
  maintenance until the shell-template DBC driver is safe enough for unattended
  use.
- DBC maintenance is staged and visible; automatic safe-window restart/client
  patch execution should stay conservative until the live shell rollback proof is
  complete.
