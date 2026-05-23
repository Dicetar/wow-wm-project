Status: DESIGN_ONLY
Last verified: 2026-05-22
Verified by: Claude
Doc type: design

# MPQ Client-Patch Auto-Apply — Design

## Goal

Publishing a visible WM spell/ability should **automatically** result in the
client `patch-z.mpq` being rebuilt and installed — without a manual
`wm.spells.client_patch build --install` step — by **queuing** the need at
publish time and **applying it when the WoW client closes** (the only moment
the locked `patch-z.mpq` can be replaced).

This extends the existing client-patch machinery; it does **not** build a
parallel patcher.

## Non-goals

- A new MPQ builder. `src/wm/spells/client_patch.py`
  (`build_client_patch_package`, `--include all`, `--install`, `--mpq-editor`)
  already materializes the client `Spell.dbc` / `SkillLineAbility.dbc` /
  `SkillRaceClassInfo.dbc` and packages/installs `patch-z.mpq`. We reuse it.
- Custom **item** icon patches — a documented gap (`wm-build-client-patch`
  skill); stays out of scope.
- Changing what `SpellPublisher.publish` does to server state.

## Existing system (what we build on)

- `src/wm/spells/client_patch.py` — `build_client_patch_package(..., install=...)`
  builds + (optionally) installs the MPQ. `materialize`/`build` CLI subcommands;
  `--include all|named`, `--install-path`, `--mpq-editor`.
- `src/wm/spells/publish.py` — `SpellPublisher.publish(*, draft, mode)` is the
  spell publish path; `mode="apply"` mutates server DBC/shell state.
- `control/runtime/spell_shell_bank.json` — source of truth for which shells
  need client DBC entries. `--include all` rebuilds from it.
- The running client **locks `patch-z.mpq`**; install must happen with
  `wow.exe` closed (proven repeatedly in the Broug pipeline).
- `scripts/client/Clear-WoWItemCache.ps1` — clears stale client cache.
- ADR-0003: built client-patch artifacts are **not committed**.

## Architecture (4 units; pure logic separated from shells)

### 1. Pending-patch store — `src/wm/spells/client_patch_pending.py`
Pure read/write/merge of `control/runtime/client_patch_pending.json`.

Contract:
```json
{
  "schema_version": "wm.client_patch_pending.v1",
  "entries": [{"spell_id": 947000, "name": "...", "reason": "spell publish", "queued_at": "<iso>"}],
  "last_applied_at": "<iso>|null"
}
```
Functions:
- `mark_pending(spell_ids: list[int], *, reason: str, names: dict[int,str] | None = None, path=None) -> dict` — merge new entries (dedupe by spell_id), write, return the state.
- `load_pending(path=None) -> dict` — read (empty/default if absent).
- `clear_pending(path=None) -> dict` — empty `entries`, set `last_applied_at=now`.

Pure + small file I/O; unit-tested with `tmp_path`.

### 2. Publish hook — `src/wm/spells/publish.py`
On a successful `SpellPublisher.publish(mode="apply")` for a visible/shell spell,
call `mark_pending([draft.spell_id], reason="spell publish", names={...})`.

**Best-effort:** wrap in try/except so a pending-write failure logs but never
fails the publish. Dry-run mode does NOT mark pending.

### 3. Apply step — `src/wm/spells/client_patch_apply.py`
`apply_pending_client_patch(*, install_path, mpq_editor=None, build_fn=build_client_patch_package, cache_clear_fn=None, pending_path=None) -> dict`:
- `load_pending`; if `entries` empty → return `{"applied": False, "reason": "nothing pending"}` (no build).
- else call `build_fn(include="all", install=True, install_path=..., mpq_editor=...)`.
  - on success → optional `cache_clear_fn()` → `clear_pending()` → return `{"applied": True, "package": ..., "cleared": [...]}`.
  - on failure (exception or non-ok result) → **do NOT clear pending** → return `{"applied": False, "error": ...}` so the next client-close retries.

`build_fn`/`cache_clear_fn` are injected so the decision logic is unit-testable
with fakes (no MPQEditor, no real client).

### 4. Watcher integration — BridgeLab watcher
The existing always-on BridgeLab watcher gains one responsibility: track
`wow.exe`; on a **running → not-running** transition, call
`apply_pending_client_patch(...)`. Process detection is a thin shell
(PowerShell `Get-Process wow` / the watcher's loop); the pending?/apply/clear
decision is the pure Python in unit 3. Apply only fires on the transition (not
every poll) and only when something is pending.

## Data flow

```
publish visible spell (apply)
  -> mark_pending(spell_id)                       # control/runtime/client_patch_pending.json
[operator plays; wow.exe open; patch-z.mpq locked]
operator closes wow.exe
  -> BridgeLab watcher: running -> not-running transition
       -> apply_pending_client_patch:
            pending? -> build_client_patch_package(include="all", install=True)
                     -> Clear-WoWItemCache
                     -> clear_pending (last_applied_at=now)
next client launch -> correct icon / name / tooltip
```

## Error handling

- Publish-hook write failure → logged, publish unaffected (server truth still ships).
- MPQ build/install failure on close → pending retained, error logged; retries
  on the next close. Never partial-clear.
- MPQEditor missing → surfaced as the build error; pending retained.
- No `wow.exe` ever seen → nothing applied (correct; nothing to unlock).

## Testing

- **Unit (pure, no MPQ/process):** pending store mark/load/clear/merge+dedupe
  (`tmp_path`); `apply_pending_client_patch` with a fake `build_fn` —
  empty→no-op-no-build, pending→build called with `include="all", install=True`,
  build-raises→pending retained + `applied False`, success→pending cleared +
  cache_clear_fn called; publish-hook marks pending on apply, not on dry-run,
  and a raising store does not break publish.
- **Integration / operator:** real MPQEditor build, real `wow.exe`-close
  detection in the BridgeLab watcher, and in-client verification that a freshly
  published shell shows the correct icon/tooltip after a close→relaunch.

## Decisions

- Scope: spell shells / visible WM spells (`Spell.dbc` family). Item icons out of scope.
- Cache clear after install: yes (`Clear-WoWItemCache.ps1`).
- Idempotency: rebuild-all; pending list is the change-signal + audit, not the patch contents.
- Built artifacts not committed (ADR-0003). `client_patch_pending.json` is
  generated runtime state and is **not committed** — add `control/runtime/` (or
  the specific file) to `.gitignore` if not already covered. Note:
  `spell_shell_bank.json` already lives in `control/runtime/` and IS tracked, so
  ignore the specific file `control/runtime/client_patch_pending.json`, not the
  whole directory.

## Out of scope / follow-ups

- Item icon client patch (existing gap).
- A panel surface showing "client patch pending / last applied" (nice-to-have;
  the pending file already makes it inspectable).
