Status: READY (repo) / live loop proven
Last verified: 2026-05-25
Verified by: Claude
Doc type: release

# WM v1 — Release Readiness & Scope Freeze

This is the authoritative release-scope doc for WM v1. It defines what v1 **is**,
what is explicitly **out**, the readiness checklist, known limitations, and the
rollback path. WM is a per-character "World Master" for a private AzerothCore
3.3.5a server: **Python decides, native C++ executes; the LLM only proposes into
a locked schema.**

## 1. What v1 is (Definition of Done)

> From the operator surface, you can: pick a live character (marker) → scope it →
> publish a bounded artifact through a typed contract → see it work in-game →
> roll it back. Proven for the **spell-shell** lane (new shell → in-client buff)
> and the **native action** lane (marker → scope → native apply → `done`).

v1 is a **single-operator tool for one private server**, not a multi-tenant
platform. "Finished" means the core loop is reliable and frozen — not that every
designed subsystem is built.

## 2. Current product lanes

### IN — v1 (supported, proven)
| Lane | State | Evidence |
|---|---|---|
| Universal WM Session (marker → scope) | WORKING (live) | marker scan → scope-latest → Astel 5408 |
| Native bridge action bus | WORKING (live) | `debug_ping` → `done` (`pong`); `player_apply_aura` 946607 → `aura_applied` |
| Spell-shell publish (server DBC + client patch, unified + audited) | WORKING (live) | new shell 946607 published end-to-end, visible in-client with correct name/icon |
| Cross-lane approval inbox (quest/item/spell/action) + rollback | WORKING (repo) | gate + `/api/wm/inbox` + `/api/wm/rollback`; live appliers wired at bootstrap |
| Content-release pipeline, reserved slots, publish log, snapshot rollback | WORKING (repo) | full suite green |
| LLM draft → proposal inbox (quest, LIVE) | WORKING | gate is the single apply chokepoint for every kind |

### OUT — deferred indefinitely (not v1)
- Platform Tracks I–III (subject recognition, Journal Layer V2, context-pack
  gap-fill, clean quest compiler, event-spine convergence) — designed, not built.
- Advanced living-world systems: nemesis / patron / legend / oath (only rumor is LIVE).
- Narrative text generation; multi-operator onboarding / distributable packaging.
- Contracting the remaining native action kinds (57/99) — add only when a content
  item needs one, never speculatively.
- LLM proposal producers for the item/spell/action lanes (apply paths exist + are
  tested, but nothing auto-fills them yet — operator authors those manually).

## 3. Release readiness checklist (verified 2026-05-25)

### Pre-release
- [x] Full test suite green — `python -m pytest -q` → **973 passed**
- [x] `python -m wm.status --validate` → OK
- [x] `python scripts/validate_agent_skills.py` → OK
- [x] `origin/main` is at `d60404f` (`docs(release): WM v1 readiness + scope freeze`)
- [x] `origin/wm/spell-publish-and-panel-v2.2` points to the same commit as `origin/main`
- [x] No local ahead/behind delta between `main` and `origin/main`
- [x] Untracked May 18 planning/tooling drift reviewed; only the pytest marker policy was promoted into v1 stabilization
- [x] No freeform-SQL / GM-command / direct-LLM mutation lanes (every apply is a typed contract)

### Live target (BridgeLab) — verified
- [x] `wm.doctor --summary` (lab ports) → **8/8 WORKING / READY**
- [x] SOAP `7879` up; worldserver pid stable; DB `33307` reachable
- [x] Marker → scope → native `debug_ping` → `done`
- [x] New shell → publish → restart → client patch → apply → **visible in-client**

### Bootstrapping a fresh environment
- [ ] Apply DB bootstrap SQL (`sql/bootstrap/*.sql`, incl. `wm_ability_tables.sql`)
- [ ] Confirm native bridge scope includes the target GUIDs
- [ ] Generated artifacts (server `Spell.dbc`, `patch-z.mpq`) are **not committed**
      (ADR 0003) — they are produced locally under `.wm-bootstrap/state/...`

## 4. Known limitations (honest)
- **Quest rollback** is not wired to the uniform `(entry, mode)` gate adapter — it
  takes a publish *plan*, so cross-lane rollback covers item/spell, not quest yet.
- **No proposal producer** for item/spell/action lanes; apply paths are tested but
  unfed by the LLM (which only generates quests in LIVE mode).
- **Worldserver restart required** for any new spell shell (DBC loads at startup;
  not hot-reloadable) — and a restart disconnects the whole realm.
- **Client patch** requires the WoW client closed (it locks `patch-z.mpq`).
- Panel internals still carry `slice_*` names; `/api/wm/session/*` is canonical
  externally. Cosmetic debt, not a blocker.
- Native action coverage is 57/99 kinds by design (see §2 OUT).

## 5. Rollback

**Triggers:** worldserver pid death or SOAP down after a change; `wm.doctor` not
READY; `shell_audit` BROKEN; a publish that doesn't appear correctly in-client.

**Procedure (by layer):**
- **Spell DBC:** restore the timestamped backup under
  `.wm-bootstrap/state/.../backups/Spell-<ts>.dbc` over the DataDir DBC, then
  restart the worldserver. (The unified publish backs up before staging.)
- **Managed quest/item/spell rows:** `wm_rollback_snapshot` + each lane's rollback
  (item/spell wired into the approval gate; `POST /api/wm/rollback`).
- **Native action effects:** dummy auras are not persisted (clear on relog);
  durable effects are tracked in `wm_active_effect`.
- **Code:** `git revert` the offending commit; the branch is small and focused.

## 6. How to run (operator quickstart)
```
# lab ports prefix every live command:
WM_WORLD_DB_PORT=33307 WM_CHAR_DB_PORT=33307 WM_SOAP_PORT=7879

# readiness
… python -m wm.doctor --summary            # must be 8/8 before any live claim
# restart worldserver (loads new Spell.dbc); confirm pid stays alive + SOAP back
scripts/bridge_lab/Restart-BridgeLabWorldServer.ps1
# operator panel (live)
… python -m wm.panel serve --live-slice
# new spell shell: follow .agents/skills/wm-create-spell-shell (unified lane)
```
DB: `127.0.0.1:33307`, `acore`/`acore`. LM Studio: `http://localhost:1234`,
model `qwen3-coder-30b-a3b-instruct`.

Default `wm.doctor --summary` uses generic local ports (`3306` / `7878`) and may
correctly report `NOT READY` when BridgeLab is running on lab ports. Use the
explicit BridgeLab env above for live operator claims. See
`docs/BRIDGELAB_OPERATOR_ENV.md`.

## 7. Sign-off
v1 is **repo-ready and live-proven** for its two core lanes, and the release branch
has landed on `origin/main` at `d60404f`. The scope in Section 2 is frozen: new
work either proves the existing loop or is explicitly added to the IN table; the
OUT list stays out unless a concrete need reopens it.
