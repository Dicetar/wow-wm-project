Status: PARTIAL
Last verified: 2026-05-24
Verified by: Claude
Doc type: handoff

# WM — Onboarding & Next Work (read this first)

You are joining **WM (World Master)**. This brief is self-contained: what the
project is, how it's built, how to run it, what works today, and what to build
next. Repo: `Dicetar/wow-wm-project`, branch `main`. After this, the deeper
chain is `AGENTS.md` → `docs/WM_PLATFORM_HANDOFF.md` → `docs/CODEX_WORKING_RULES.md`
and the skills under `.agents/skills/`.

---

## 1. What WM is

WM is an **external-first, per-character "World Master"** for AzerothCore 3.3.5a:
a system that watches a player, decides what should happen for *them*, and makes
it real in the live game — custom quests, item-granted powers, visible spells,
companions, reactive bounties, living-world events — under strict, auditable
contracts. The long arc: personal story arcs, exclusive rewards, and an LLM that
*proposes* content which a human approves before it ships. The LLM never mutates
the game directly; it proposes into a locked schema.

## 2. Architecture (the one rule that explains everything)

**Python decides; native C++ executes. They never blur.**

- **Python (`src/wm/`)** owns: the event spine, decision/state machines, content
  validation, the publish/rollback pipelines (quests/items/spells), arc logic,
  journal/context packs, the operator panel, and the LLM proposal lane.
- **Native AzerothCore modules (`native_modules/`)** own: sensing, **typed atomic
  actions**, and shell-bound runtime spell behavior.
  - `mod-wm-bridge` — the **action bus**: Python writes typed rows to
    `wm_bridge_action_request`; the worldserver executes them (registry +
    per-domain handler files). Every capability is a registered `action_kind`.
  - `mod-wm-spells` — runtime behavior for WM-owned "shell" spells.
- **Content pipeline**: strict JSON schemas + release gates (feasibility tiers
  T1–T4), reserved-ID slots, rollback snapshots, publish logs. No freeform SQL /
  GM-command / direct-LLM mutation lanes — ever.
- **Client vs server truth (critical for spells/items):** the **server** decides
  a spell exists and applies it (loads `Spell.dbc` from its DataDir); the
  **client** only renders its icon/name/tooltip (from `patch-z.mpq`). A spell
  needs **both**, published consistently, or it's broken.

## 3. How to run it

The **Lab** (`D:\WOW\WM_BridgeLab`) is the only test target. Its worldserver
loads DBCs from `DataDir = D:\WOW\Azerothcore_WoTLK_Rebuild\run\data` (so the
"Rebuild" tree is both the clean baseline *and* the Lab's live DBC source).

| Need | Command |
|---|---|
| Run tests (must be green, no `--ignore`) | `python -m pytest -q` → 940 passed |
| BridgeLab ports (prefix live commands) | `WM_WORLD_DB_PORT=33307 WM_CHAR_DB_PORT=33307 WM_SOAP_PORT=7879` |
| Live readiness | `…ports… python -m wm.doctor --summary` (default checks 3306/7878 — must pass the ports or it false-FAILs) |
| Restart worldserver | `scripts/bridge_lab/Restart-BridgeLabWorldServer.ps1` then poll SOAP; **verify the pid stays alive** after boot |
| Operator panel (live) | `…ports… python -m wm.panel serve --live-slice` |
| LM Studio | `http://localhost:1234`; use **`qwen3-coder-30b-a3b-instruct`** (instruct model — RP models return empty under JSON-schema) |
| WM CLI catalog | `python -m wm.cli --list` |

DB: `127.0.0.1:33307`, `acore`/`acore`, `acore_world` / `acore_characters`.
Bash cwd is often `D:\WOW` — use `cd /d/WOW/wm-project && …`. Don't put backticks
in bash-embedded SQL.

## 4. What works today (honest labels)

- **Repo/CI**: `WORKING` — full suite green & repeatable.
- **Event spine, control contracts, journal, context packs, content-release
  pipeline, reserved-slot/rollback tooling, operator panel**: `WORKING` at
  repo/API level (see `WM_PLATFORM_HANDOFF.md` for per-feature detail).
- **LLM quest loop**: `WORKING` live — an arc beat → LM Studio generates a
  kill-bounty → screen/validate → publish → grant. Proven in-client (quest
  910213 in a character's log). New quests need a **worldserver restart** to
  become grantable.
- **Universal operator panel V2.1**: `WORKING` (read-side) — discovers/selects
  the marker-scoped character and shows its state via `/api/wm/session/overview`;
  a guard test forbids hardcoded test GUIDs in generic code.
- **Client MPQ auto-patch**: `WORKING` — publishing a spell queues a patch; the
  watcher rebuilds+installs `patch-z.mpq` when the client closes.
- **Watcher marker (946602)**: `WORKING` — a permanent buff-panel marker (no VFX,
  no gameplay), applied via the bridge.
- **Spell/ability *server-side* publish**: `INCOMPLETE` — see §5.1. All 26 spell
  shells are `patch_state: "planned"`; Broug abilities/Energy Surge are
  static-validated only, **not** combat-proven live.

## 5. What to build next (in priority order)

### 5.1 Unify the spell publish pipeline  ← start here
Client and server spell definitions are published by separate, inconsistent
paths and drift (e.g. the server materializer keeps the cloned seed's name; a
shell shipped invisible due to a 0-duration). Make it one coherent lane:
- `src/wm/spells/server_dbc.py::materialize_server_spell_dbc` must **author
  name + tooltip + duration from the shell bank** (mirror
  `client_patch.py` ~L867–872), not reuse the seed's string block.
- Add `wm.spells.shell_audit` rules that fail on: visible-buff shell with
  `duration_index 0`; dummy aura with no spell-visual when a buff is intended;
  missing/seed-leaked name.
- Add one **client+server publish** command that materializes both, reads both
  rows back, asserts name/icon/duration agree, stages the server `Spell.dbc`
  (backup first) + queues the client patch, then verify on one spell.
- Then publish the 26 "planned" shells properly and re-verify Broug/Energy Surge
  live. (Refs: shell bank `control/runtime/spell_shell_bank.json`; SpellDuration
  index 21 = infinite; Spell.dbc field offsets are constants in `server_dbc.py`.)

### 5.2 Panel V2.2 — generic cross-lane approval
One operator inbox to approve any managed quest/item/spell/action proposal →
publish/apply/rollback through existing contracts (builds on `/api/wm/session/*`,
`/api/jobs/*`, the control-proposal system).

### 5.3 Slice loop robustness
Handle "new quest needs worldserver restart" in `SlicePublishService`; wire the
reactive **watcher LIVE generation** (map recipe/slots → fixed publish facts via
`wm.targets.resolver`); fix the published-but-not-granted retry (re-approval
orphans the first published quest) in `src/wm/cli/slice_publish.py`.

### 5.4 Marker migration cleanup
Finish `946500`→`946602` consistently across server, client, and tooling; retire
`946500`.

## 6. Operating facts you must know
- Verify against the source the **runtime uses**: the `spell_dbc` *table* is
  stale and is NOT the server's spell source — the `Spell.dbc` *file* in the
  DataDir is.
- "repo WORKING" ≠ "gameplay WORKING". Prove spells/items live before claiming so.
- Native aura/quest actions require the target **online** when the worldserver
  poller runs them; dummy auras are not saved to `character_aura` (normal).
- After a worldserver restart, confirm the pid stays alive (a rapid double-restart
  once booted to `AC>` then died).

## 7. Where things live
- Slice LLM loop: `src/wm/llm/proposal_adapter.py`, `src/wm/cli/{slice_demo,slice_demo_live,slice_publish}.py`, `src/wm/panel/slice_wiring.py`.
- Quest publish: `src/wm/quests/{publish/__init__.py,live_publish.py,validator.py,models.py}`.
- Spells (§5.1): `src/wm/spells/{server_dbc,client_patch,client_patch_apply,client_patch_pending,publish,shell_audit}.py`, `control/runtime/spell_shell_bank.json`.
- Panel: `src/wm/panel/{server,catalog,state}.py`, `static/{index.html,app.js}`; watcher: `src/wm/events/watch.py`.
- Native: `native_modules/mod-wm-bridge/`, `native_modules/mod-wm-spells/`.
- Designs/plans (recent): `docs/superpowers/specs|plans/2026-05-22-*`.
- **Untracked, leave alone:** the abilities track (`src/wm/abilities/{__init__,models,tracker}.py` + its test), `docs/superpowers/*2026-05-18*`, `scripts/phase0/`, `sql/bootstrap/wm_ability_tables.sql`.

End of handoff.
