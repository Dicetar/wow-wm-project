Status: PARTIAL
Last verified: 2026-05-23
Verified by: Codex
Doc type: status

# WM Control Panel + LM Studio V1

This is the current local operator console for WM. The primary operator surface
is now **WM Session**, not a character-specific Broug/Jecia or vertical-slice
screen. Broug and Jecia remain useful fixtures, not architecture.

Start it from the repo root:

```powershell
python -m wm.panel --host 127.0.0.1 --port 8765
```

The panel is local-only and binds to `127.0.0.1` by default. It is a thin shell over existing WM CLIs and schemas. It must not accept raw shell commands, freeform SQL, freeform GM commands, config edits, or direct LLM mutation lanes.

## Current Scope

Backend modules live under `src/wm/panel/`:

- `server.py` - stdlib HTTP API and static asset serving
- `catalog.py` - allowlisted command catalog
- `jobs.py` - dry-run/apply job runner and state machine
- `schemas.py` - schema catalog loading and JSON-schema validation
- `state.py` - `.wm-bootstrap/state/control-panel/` persistence
- `static/` - vanilla HTML/CSS/JS UI
- `schemas/catalog.json` - one contract for forms, LLM structured output, and validation routing

LM Studio support lives under `src/wm/llm/`:

- `lmstudio.py` - OpenAI-compatible `/v1/models` and `/v1/chat/completions` client
- `prompts.py` - WM draft prompt construction
- `results.py` - structured response parsing/result helpers

Panel state is stored under:

```text
.wm-bootstrap/state/control-panel/
  settings.json
  jobs/
  drafts/
  schemas/
  artifacts/
  session.json
```

`settings.json` is preserved across runs. API keys are memory-only in v1.
`session.json` stores the active operator-selected character session.

## Covered APIs

```text
GET  /
GET  /api/status
GET  /api/catalog
GET  /api/jobs/<job_id>
POST /api/jobs/dry-run
POST /api/jobs/apply
GET  /api/schemas
GET  /api/schemas/<schema_version>
POST /api/schema/validate
GET  /api/llm/settings
POST /api/llm/settings
GET  /api/llm/models
POST /api/llm/generate
GET  /api/drafts
GET  /api/drafts/<draft_id>
POST /api/drafts/<draft_id>/adopt
POST /api/drafts/<draft_id>/reject
GET  /api/wm/readiness
GET  /api/wm/markers
POST /api/wm/session/bootstrap
GET  /api/wm/session/status
GET  /api/wm/session/pending
GET  /api/wm/session/issues
GET  /api/wm/session/log
POST /api/wm/session/poll
POST /api/wm/session/approve
POST /api/wm/session/reject
```

`/api/slice/*` remains as a compatibility alias for one release. New code and
docs should use `/api/wm/session/*`.

## WM Session Flow

The session can be bootstrapped in two ways:

- explicit `character_guid`
- recent marker aura discovery

The canonical marker spell is `946602` (`WM Watcher Beacon`), imported from
`wm.sources.native_bridge.player_marker.DEFAULT_MARKER_SPELL_ID`. The panel may
override the marker spell per request, but defaults must stay aligned with the
native marker CLI.

Active session metadata persisted by the panel:

```text
character_guid
character_name
source = explicit_guid | marker
marker_spell_id
bridge_event_id
selected_at
marker
```

The panel exposes marker workflow commands through the normal job gate:

- `marker.scan` - read-only marker discovery
- `marker.scope_latest` - mutating, dry-run required, type-job-id confirmation
- `marker.observe_all.start` / `marker.observe_all.stop` - optional temporary
  wildcard observation through the existing bridge configure command, also gated

No raw SQL, raw GM command, shell command, config-edit, or direct LLM live
mutation lane is added.

## Schema Catalog

Initial schema versions:

- `control.proposal.v1`
- `wm.quest.release.repeatable_bounty.v1`
- `wm.quest.release.one_shot.v1`
- `wm.quest.release.story_arc.v1`
- `wm.item.release.managed_power.v1`
- `wm.ability.release.shell_power.v1`
- `wm.scene.release.native_sequence.v1`

The content schemas use existing release field `schema_version`, not `schema_id`.

The GUI renders forms directly from the catalog. Enum fields render as dropdowns, including managed item shape, inventory slot, quality, binding, effect trigger/target, ability shell family, scene type, trigger kind, reward kind, and quest grant mode where the validator already supports those values.

## LLM Draft Lifecycle

LLM output is draft-only.

```text
LM Studio response
  -> raw response captured
  -> JSON content parsed
  -> schema validation
  -> draft state VALIDATED | INVALID | BROKEN
```

Malformed JSON becomes `BROKEN`. Schema-invalid JSON becomes `INVALID`. A valid LLM draft still cannot be run directly. The operator must use "Adopt as reviewed", which creates a human-reviewed draft copy and preserves the original LLM metadata.

## Job Lifecycle

Jobs use this state vocabulary:

```text
DRAFT
VALIDATED
DRY_RUN_PASSED
AWAITING_CONFIRM
APPLIED
REJECTED
INVALID
BROKEN
```

Mutating commands require dry-run first. Apply requires explicit confirmation by typing the job id when the catalog entry demands it. A failed confirmation is recorded as an apply attempt but does not burn the dry-run job.

The job runner uses fixed argv templates and `subprocess.run(..., shell=False)`.

## Path Safety

Context pack and candidate pack file inputs are constrained to the WM workspace. Repo-local paths and paths under `.wm-bootstrap/state/control-panel/` are allowed because they resolve inside the workspace. Absolute paths outside the workspace are rejected.

## Known Gaps

- Browser visual smoke remains `PARTIAL`: the local API smoke passed on
  `127.0.0.1:8766`, but the Codex in-app browser refused navigation to that
  local URL under its security policy.
- Universal explicit-GUID API proof is `WORKING`: panel job
  `job-20260522221357-59927577` dry-ran and approved a `debug_ping` control
  proposal for session GUID `5406`; native request `702` reached `done`.
  Marker-selection UI proof remains `PARTIAL` because no recent `946602`
  marker candidate was present in the lab.
- The current release flow reaches validate/plan/packet and job gates; live apply is intentionally routed through existing owned commands and still needs lane-by-lane proof.
- Context-pack generation and target recognition are still CLI-first; deeper UI selectors are future work.
- LM Studio behavior depends on the local model honoring JSON-schema structured output.
- Gameplay proof is not implied by API tests; see [Live Proof Backlog](LIVE_PROOF_BACKLOG.md).
