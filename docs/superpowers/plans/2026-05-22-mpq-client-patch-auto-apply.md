# MPQ Client-Patch Auto-Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publishing a managed spell queues a client-patch need; the BridgeLab watcher rebuilds + installs `patch-z.mpq` automatically the moment `wow.exe` closes (when the lock is released), then clears the queue.

**Architecture:** A pure pending-state store (`control/runtime/client_patch_pending.json`) is written best-effort by `SpellPublisher.publish` on apply. A pure apply step calls the *existing* `build_client_patch_package(include="all", install_path=...)`, clears the WoW cache, and clears pending — keeping pending on failure. A small edge-detector folded into the `wm.events.watch` loop fires the apply on a `wow.exe` running→closed transition. All decision logic is dependency-injected and unit-tested; only the OS process-probe and the real MPQ build are integration.

**Tech Stack:** Python 3.14, `pytest`, stdlib `subprocess`, existing `wm.spells.client_patch`. Spec: `docs/superpowers/specs/2026-05-22-mpq-client-patch-auto-apply-design.md`.

**Run focused tests:** `python -m pytest <path> -q`. Full suite: `python -m pytest -q` (baseline 928 passed; must stay green, no `--ignore`).

---

## File structure

- Create `src/wm/spells/client_patch_pending.py` — pending-state store (pure + small file I/O).
- Create `src/wm/spells/client_patch_apply.py` — `apply_pending_client_patch(...)`, `ClientPatchCloseWatcher` edge-detector, and a `main()` CLI.
- Modify `src/wm/spells/publish.py` — best-effort publish hook.
- Modify `src/wm/events/watch.py` — fold the close-detector into the loop behind a flag.
- Modify `.gitignore` — ignore `control/runtime/client_patch_pending.json`.
- Tests: `tests/spells/test_client_patch_pending.py`, `tests/spells/test_client_patch_apply.py`, `tests/spells/test_publish_client_patch_hook.py`, extend `tests/test_event_watch.py`.

---

## Task 1: Pending-patch store

**Files:**
- Create: `src/wm/spells/client_patch_pending.py`
- Test: `tests/spells/test_client_patch_pending.py` (create `tests/spells/__init__.py` if missing for discovery)

- [ ] **Step 1: Write the failing test**

```python
# tests/spells/test_client_patch_pending.py
from wm.spells.client_patch_pending import mark_pending, load_pending, clear_pending


def test_mark_load_clear_roundtrip(tmp_path):
    p = tmp_path / "client_patch_pending.json"
    assert load_pending(path=p)["entries"] == []

    st = mark_pending([947000], reason="spell publish", names={947000: "Cloud Step"}, path=p)
    assert st["schema_version"] == "wm.client_patch_pending.v1"
    assert [e["spell_id"] for e in st["entries"]] == [947000]
    assert st["entries"][0]["name"] == "Cloud Step"
    assert st["entries"][0]["reason"] == "spell publish"
    assert "queued_at" in st["entries"][0]

    # second mark dedupes by spell_id, keeps one entry, adds a new one
    st = mark_pending([947000, 947001], reason="spell publish", path=p)
    assert sorted(e["spell_id"] for e in st["entries"]) == [947000, 947001]

    assert load_pending(path=p)["entries"]  # persisted
    cleared = clear_pending(path=p)
    assert cleared["entries"] == []
    assert cleared["last_applied_at"] is not None
    assert load_pending(path=p)["entries"] == []
```

- [ ] **Step 2: Run it — FAIL** (`ModuleNotFoundError`).

Run: `python -m pytest tests/spells/test_client_patch_pending.py -q`

- [ ] **Step 3: Implement `src/wm/spells/client_patch_pending.py`**

```python
"""Pending client-patch state.

Records that a managed spell publish has made the client MPQ stale, so the
apply-on-close step knows it must rebuild + install. Pure read/write/merge of a
small JSON file; the file is generated runtime state (not committed)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "wm.client_patch_pending.v1"


def default_pending_path() -> Path:
    return Path(__file__).resolve().parents[3].joinpath("control", "runtime", "client_patch_pending.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "entries": [], "last_applied_at": None}


def load_pending(*, path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else default_pending_path()
    if not p.exists():
        return _empty()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    raw.setdefault("schema_version", SCHEMA_VERSION)
    raw.setdefault("entries", [])
    raw.setdefault("last_applied_at", None)
    return raw


def _write(p: Path, state: dict[str, Any]) -> dict[str, Any]:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return state


def mark_pending(spell_ids: list[int], *, reason: str,
                 names: dict[int, str] | None = None,
                 path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else default_pending_path()
    state = load_pending(path=p)
    names = names or {}
    by_id = {int(e["spell_id"]): e for e in state["entries"] if "spell_id" in e}
    for sid in spell_ids:
        sid = int(sid)
        by_id[sid] = {
            "spell_id": sid,
            "name": names.get(sid, by_id.get(sid, {}).get("name", "")),
            "reason": reason,
            "queued_at": _now_iso(),
        }
    state["entries"] = [by_id[k] for k in sorted(by_id)]
    return _write(p, state)


def clear_pending(*, path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else default_pending_path()
    state = load_pending(path=p)
    state["entries"] = []
    state["last_applied_at"] = _now_iso()
    return _write(p, state)
```

- [ ] **Step 4: Run — PASS.** `python -m pytest tests/spells/test_client_patch_pending.py -q`

- [ ] **Step 5: Commit**

```bash
git add src/wm/spells/client_patch_pending.py tests/spells/test_client_patch_pending.py tests/spells/__init__.py
git commit -m "feat(spells): client-patch pending-state store"
```

---

## Task 2: Apply step

**Files:**
- Create: `src/wm/spells/client_patch_apply.py`
- Test: `tests/spells/test_client_patch_apply.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/spells/test_client_patch_apply.py
import pytest
from wm.spells.client_patch_apply import apply_pending_client_patch
from wm.spells.client_patch_pending import mark_pending, load_pending


def _build_ok(**kwargs):
    return {"ok": True, "kwargs": kwargs}


def test_apply_noop_when_nothing_pending(tmp_path):
    p = tmp_path / "pending.json"
    calls = []
    out = apply_pending_client_patch(pending_path=p, build_fn=lambda **k: calls.append(k))
    assert out["applied"] is False
    assert out["reason"] == "nothing pending"
    assert calls == []


def test_apply_builds_installs_and_clears_when_pending(tmp_path):
    p = tmp_path / "pending.json"
    mark_pending([947000], reason="spell publish", path=p)
    build_calls, cache_calls = [], []

    out = apply_pending_client_patch(
        pending_path=p,
        install_path="C:/WoW/Data",
        build_fn=lambda **k: build_calls.append(k) or _build_ok(**k),
        cache_clear_fn=lambda: cache_calls.append(True),
    )
    assert out["applied"] is True
    assert build_calls and build_calls[0]["include"] == "all"
    assert build_calls[0]["install_path"] == "C:/WoW/Data"
    assert cache_calls == [True]
    assert load_pending(path=p)["entries"] == []  # cleared


def test_apply_keeps_pending_on_build_failure(tmp_path):
    p = tmp_path / "pending.json"
    mark_pending([947000], reason="spell publish", path=p)

    def boom(**k):
        raise RuntimeError("MPQEditor missing")

    out = apply_pending_client_patch(pending_path=p, install_path="C:/WoW/Data", build_fn=boom)
    assert out["applied"] is False
    assert "MPQEditor missing" in out["error"]
    assert load_pending(path=p)["entries"]  # NOT cleared -> retries next close
```

- [ ] **Step 2: Run it — FAIL** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `src/wm/spells/client_patch_apply.py`**

```python
"""Apply pending client patches when it is safe (client closed).

Decision + orchestration only; the actual MPQ build/install is the existing
wm.spells.client_patch.build_client_patch_package, injected as build_fn so the
logic is unit-testable without MPQEditor or a real client."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

from wm.spells.client_patch_pending import load_pending, clear_pending


def _default_build_fn(**kwargs: Any) -> Any:
    from wm.spells.client_patch import (
        build_client_patch_package, default_source_dbc_path,
        default_package_path, default_mpq_editor_path, default_install_path,
    )
    kwargs.setdefault("source_dbc", str(default_source_dbc_path()))
    kwargs.setdefault("package_out", str(default_package_path()))
    kwargs.setdefault("mpq_editor", str(default_mpq_editor_path()))
    if kwargs.get("install_path") is None:
        kwargs["install_path"] = str(default_install_path())
    return build_client_patch_package(**kwargs)


def _default_cache_clear() -> None:
    script = Path(__file__).resolve().parents[3].joinpath("scripts", "client", "Clear-WoWItemCache.ps1")
    if not script.exists():
        return
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, text=True, check=False,
    )


def apply_pending_client_patch(
    *,
    install_path: str | Path | None = None,
    mpq_editor: str | Path | None = None,
    pending_path: str | Path | None = None,
    build_fn: Callable[..., Any] = _default_build_fn,
    cache_clear_fn: Callable[[], None] = _default_cache_clear,
) -> dict[str, Any]:
    state = load_pending(path=pending_path)
    if not state["entries"]:
        return {"applied": False, "reason": "nothing pending"}

    spell_ids = [int(e["spell_id"]) for e in state["entries"]]
    build_kwargs: dict[str, Any] = {"include": "all"}
    if install_path is not None:
        build_kwargs["install_path"] = install_path
    if mpq_editor is not None:
        build_kwargs["mpq_editor"] = mpq_editor

    try:
        result = build_fn(**build_kwargs)
    except Exception as exc:  # build/install/MPQEditor failure -> keep pending
        return {"applied": False, "error": str(exc), "spell_ids": spell_ids}

    try:
        cache_clear_fn()
    except Exception:
        pass  # cache clear is best-effort; the patch is already installed

    clear_pending(path=pending_path)
    return {"applied": True, "spell_ids": spell_ids, "result": result}
```

NOTE: `build_client_patch_package` installs when `install_path` is non-None (there is no `install` bool). The test injects `build_fn`, so the real signature is only exercised via `_default_build_fn`.

- [ ] **Step 4: Run — PASS.** `python -m pytest tests/spells/test_client_patch_apply.py -q`

- [ ] **Step 5: Commit**

```bash
git add src/wm/spells/client_patch_apply.py tests/spells/test_client_patch_apply.py
git commit -m "feat(spells): apply-pending client patch (rebuild-all+install, keep-on-failure)"
```

---

## Task 3: Close-transition edge detector

**Files:**
- Modify: `src/wm/spells/client_patch_apply.py` (add `ClientPatchCloseWatcher`)
- Test: `tests/spells/test_client_patch_apply.py` (extend)

- [ ] **Step 1: Write the failing test** (append)

```python
def test_close_watcher_fires_only_on_running_to_closed_edge():
    from wm.spells.client_patch_apply import ClientPatchCloseWatcher
    fired = []
    w = ClientPatchCloseWatcher(apply_fn=lambda: fired.append(True) or {"applied": True})
    # not running yet -> no fire
    assert w.tick(running=False) is None
    # starts running -> no fire
    assert w.tick(running=True) is None
    # still running -> no fire
    assert w.tick(running=True) is None
    # closed (running -> not running) -> FIRE once
    assert w.tick(running=False) == {"applied": True}
    # stays closed -> no repeat fire
    assert w.tick(running=False) is None
    assert fired == [True]


def test_close_watcher_handles_open_close_open_close():
    from wm.spells.client_patch_apply import ClientPatchCloseWatcher
    fired = []
    w = ClientPatchCloseWatcher(apply_fn=lambda: fired.append(1) or {})
    for running in (True, False, True, False):
        w.tick(running=running)
    assert fired == [1, 1]  # two close edges
```

- [ ] **Step 2: Run — FAIL** (`ImportError: ClientPatchCloseWatcher`).

- [ ] **Step 3: Implement** (append to `client_patch_apply.py`)

```python
class ClientPatchCloseWatcher:
    """Fires apply_fn on each wow.exe running -> not-running transition.

    Pure edge logic: the caller feeds `running` (from any process probe) each
    tick; we only fire when the previous tick was running and this one is not.
    """
    def __init__(self, *, apply_fn: Callable[[], Any]) -> None:
        self._apply_fn = apply_fn
        self._was_running = False

    def tick(self, *, running: bool) -> Any | None:
        fired = None
        if self._was_running and not running:
            fired = self._apply_fn()
        self._was_running = running
        return fired
```

- [ ] **Step 4: Run — PASS.** `python -m pytest tests/spells/test_client_patch_apply.py -q`

- [ ] **Step 5: Commit**

```bash
git add src/wm/spells/client_patch_apply.py tests/spells/test_client_patch_apply.py
git commit -m "feat(spells): client-patch close-transition edge detector"
```

---

## Task 4: Publish hook (best-effort)

**Files:**
- Modify: `src/wm/spells/publish.py` (`SpellPublisher.publish`)
- Test: `tests/spells/test_publish_client_patch_hook.py`

READ FIRST: `src/wm/spells/publish.py` `publish(*, draft, mode) -> SpellPublishResult` — it returns a result with `.applied`; the spell identity it uses is `draft.spell_entry`. Confirm both before wiring.

- [ ] **Step 1: Write the failing test**

```python
# tests/spells/test_publish_client_patch_hook.py
from wm.spells import publish as publish_mod
from wm.spells.client_patch_pending import load_pending


def test_publish_marks_pending_on_apply(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(publish_mod, "mark_pending",
                        lambda spell_ids, **k: calls.append((list(spell_ids), k)))
    publish_mod._note_client_patch_pending(spell_entry=947000, mode="apply", applied=True)
    assert calls and calls[0][0] == [947000]
    assert calls[0][1]["reason"]


def test_publish_does_not_mark_on_dry_run_or_not_applied(monkeypatch):
    calls = []
    monkeypatch.setattr(publish_mod, "mark_pending", lambda spell_ids, **k: calls.append(1))
    publish_mod._note_client_patch_pending(spell_entry=947000, mode="dry-run", applied=False)
    publish_mod._note_client_patch_pending(spell_entry=947000, mode="apply", applied=False)
    assert calls == []


def test_publish_hook_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(publish_mod, "mark_pending", boom)
    # must not raise
    publish_mod._note_client_patch_pending(spell_entry=947000, mode="apply", applied=True)
```

- [ ] **Step 2: Run — FAIL** (`AttributeError: _note_client_patch_pending`).

- [ ] **Step 3: Implement the hook in `publish.py`**

At the top of `publish.py`, add the import:
```python
from wm.spells.client_patch_pending import mark_pending
```
Add the helper at module scope:
```python
def _note_client_patch_pending(*, spell_entry: int, mode: str, applied: bool) -> None:
    """Best-effort: queue a client-patch rebuild after a real spell publish.
    Never let a pending-write failure break publishing."""
    if mode != "apply" or not applied:
        return
    try:
        mark_pending([int(spell_entry)], reason="spell publish")
    except Exception:
        pass
```
Then in `SpellPublisher.publish`, immediately before the `return SpellPublishResult(...)` of the **apply success** path (the branch where `applied=True`), call:
```python
        _note_client_patch_pending(spell_entry=draft.spell_entry, mode=mode, applied=True)
```
(Read the method to place it on the success path only — not the dry-run/failed early return. If the result object is built first, call the hook with `applied=result.applied` just before returning it.)

- [ ] **Step 4: Run — PASS.** `python -m pytest tests/spells/test_publish_client_patch_hook.py -q` then `python -m pytest tests/ -k "spell" -q` for no regression.

- [ ] **Step 5: Commit**

```bash
git add src/wm/spells/publish.py tests/spells/test_publish_client_patch_hook.py
git commit -m "feat(spells): publish marks client-patch pending on apply (best-effort)"
```

---

## Task 5: Manual apply CLI

**Files:**
- Modify: `src/wm/spells/client_patch_apply.py` (add `main`)
- Test: `tests/spells/test_client_patch_apply.py` (extend)

- [ ] **Step 1: Write the failing test** (append)

```python
def test_cli_apply_now_invokes_apply(tmp_path, monkeypatch, capsys):
    import wm.spells.client_patch_apply as mod
    called = {}
    monkeypatch.setattr(mod, "apply_pending_client_patch",
                        lambda **k: called.update(k) or {"applied": False, "reason": "nothing pending"})
    rc = mod.main(["--install-path", "C:/WoW/Data"])
    assert rc == 0
    assert called["install_path"] == "C:/WoW/Data"
    assert "applied" in capsys.readouterr().out
```

- [ ] **Step 2: Run — FAIL** (`AttributeError: main`).

- [ ] **Step 3: Implement `main`** (append to `client_patch_apply.py`)

```python
def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    p = argparse.ArgumentParser(prog="python -m wm.spells.client_patch_apply",
                                description="Apply the pending client patch now (build-all + install).")
    p.add_argument("--install-path", default=None)
    p.add_argument("--mpq-editor", default=None)
    args = p.parse_args(argv)
    out = apply_pending_client_patch(install_path=args.install_path, mpq_editor=args.mpq_editor)
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: Run — PASS.** `python -m pytest tests/spells/test_client_patch_apply.py -q`

- [ ] **Step 5: Commit**

```bash
git add src/wm/spells/client_patch_apply.py tests/spells/test_client_patch_apply.py
git commit -m "feat(spells): client_patch_apply CLI (manual apply-now)"
```

---

## Task 6: Fold close-detection into the watch loop + gitignore

**Files:**
- Modify: `src/wm/events/watch.py`
- Modify: `.gitignore`
- Test: `tests/test_event_watch.py` (extend)

READ FIRST: `src/wm/events/watch.py` — `main()` builds args via `_build_parser()`, then runs `while True:` (around line 121) calling `execute_event_spine(...)` each iteration with `time.sleep(args.interval_seconds)`. You will add: (a) a `--client-patch-on-close` flag (default False) + `--client-install-path`; (b) a process-probe helper; (c) a `ClientPatchCloseWatcher` instance ticked each iteration when the flag is on.

- [ ] **Step 1: Write the failing test** (append to `tests/test_event_watch.py`)

```python
def test_wow_running_probe_returns_bool(monkeypatch):
    import wm.events.watch as watch
    # tasklist output containing wow.exe -> True
    monkeypatch.setattr(watch, "_run_tasklist", lambda: "wow.exe  1234 Console")
    assert watch._wow_client_running() is True
    monkeypatch.setattr(watch, "_run_tasklist", lambda: "INFO: No tasks are running")
    assert watch._wow_client_running() is False
```

- [ ] **Step 2: Run — FAIL** (`AttributeError`).

- [ ] **Step 3: Add the probe + helpers to `watch.py`**

Add near the top-level helpers:
```python
def _run_tasklist() -> str:
    import subprocess
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq wow.exe"],
                             capture_output=True, text=True, check=False)
        return out.stdout or ""
    except Exception:
        return ""


def _wow_client_running() -> bool:
    return "wow.exe" in _run_tasklist().lower()
```

- [ ] **Step 4: Run that test — PASS.** `python -m pytest tests/test_event_watch.py -k wow_running -q`

- [ ] **Step 5: Wire the watcher into the loop**

In `_build_parser()` add:
```python
    parser.add_argument("--client-patch-on-close", action="store_true",
                        help="Rebuild+install the client MPQ when wow.exe closes, if a patch is pending.")
    parser.add_argument("--client-install-path", default=None)
```
In `main()`, before `iteration = 0`:
```python
    close_watcher = None
    if getattr(args, "client_patch_on_close", False):
        from wm.spells.client_patch_apply import ClientPatchCloseWatcher, apply_pending_client_patch
        close_watcher = ClientPatchCloseWatcher(
            apply_fn=lambda: apply_pending_client_patch(install_path=args.client_install_path))
```
Inside the `while True:` loop, after the existing per-iteration work and before `time.sleep(...)` (place it so it runs every iteration regardless of event activity — e.g. right after the `except` block, just before the `max_iterations`/`sleep` tail), add:
```python
            if close_watcher is not None:
                try:
                    result = close_watcher.tick(running=_wow_client_running())
                    if result is not None and args.summary:
                        print(f"client_patch_on_close applied={result.get('applied')} "
                              f"detail={result}", flush=True)
                except Exception as exc:
                    _emit_watch_iteration_error(iteration=iteration, adapter_name=args.adapter,
                                                mode=args.mode, player_guid=args.player_guid, exc=exc)
```
(Read the loop tail to insert at a point reached on BOTH the success and the `continue` paths — simplest is just before the final `time.sleep`. Match the real variable names; `_emit_watch_iteration_error`'s signature is shown at watch.py:139.)

- [ ] **Step 6: Add a loop-integration test** (append) — drive `main` with `--max-iterations` and a fake probe/apply to prove the wiring fires on a close edge:

```python
def test_watch_loop_applies_client_patch_on_close(monkeypatch):
    import wm.events.watch as watch
    # avoid real spine work
    monkeypatch.setattr(watch, "execute_event_spine", lambda **k: {"polled_count": 0})
    # simulate wow.exe running then closing across iterations
    seq = iter([True, False])
    monkeypatch.setattr(watch, "_wow_client_running", lambda: next(seq, False))
    applied = []
    import wm.spells.client_patch_apply as apply_mod
    monkeypatch.setattr(apply_mod, "apply_pending_client_patch",
                        lambda **k: applied.append(k) or {"applied": True})
    rc = watch.main(["--adapter", "native_bridge", "--mode", "observe",
                     "--client-patch-on-close", "--max-iterations", "2",
                     "--interval-seconds", "0", "--player-guid", "5405"])
    assert rc == 0
    assert applied  # fired on the running->closed edge
```

NOTE: match the real `_build_parser` flags for `--adapter/--mode/--player-guid/--max-iterations/--interval-seconds`; read the parser first and adjust the argv to valid values. If `observe` mode still needs DB, also monkeypatch whatever `main` calls before the loop (the test must not hit MySQL). Keep the test hermetic.

- [ ] **Step 7: gitignore the pending file**

Add to `.gitignore`:
```
control/runtime/client_patch_pending.json
```

- [ ] **Step 8: Run** `python -m pytest tests/test_event_watch.py -q` — PASS, no regressions.

- [ ] **Step 9: Commit**

```bash
git add src/wm/events/watch.py tests/test_event_watch.py .gitignore
git commit -m "feat(watch): apply pending client patch on wow.exe close (BridgeLab watcher)"
```

---

## Task 7: Full suite + skills + invariant

- [ ] **Step 1: Full suite twice** — `python -m pytest -q` then again. Expect green (≥ 928 + new tests), no `--ignore`.
- [ ] **Step 2:** `python scripts/validate_agent_skills.py` (OK) and `python -m wm.status --validate` (OK). If the `wm-build-client-patch` skill should mention the auto-apply lane, update it (skill edit → re-validate).
- [ ] **Step 3:** confirm the GUID guard still passes: `python -m pytest tests/test_no_hardcoded_test_guids.py -q`.
- [ ] **Step 4: Commit any fixups** `git add -u && git commit -m "test: green full suite for MPQ client-patch auto-apply"`.

---

## Live-proof (deferred, operator + BridgeLab)

With BridgeLab up and the native watcher launched with `--client-patch-on-close --client-install-path "<WoW>\Data"`: publish a managed spell (apply) → confirm `control/runtime/client_patch_pending.json` has the entry → close `wow.exe` → confirm the watcher rebuilt + installed `patch-z.mpq`, cleared the cache, and emptied pending → relaunch and confirm the spell's icon/tooltip is correct in-client. Record in `docs/LIVE_PROOF_BACKLOG.md`. No gameplay `WORKING` until this passes.

---

## Self-review notes

- **Spec coverage:** pending store → Task 1; apply step (rebuild-all + install + cache-clear + keep-on-failure) → Task 2; close-edge detection → Task 3; publish-time dirty-flag (best-effort) → Task 4; manual apply → Task 5; watcher integration + gitignore → Task 6; suite/skills → Task 7. Scope (spells only) and item-icon non-goal are inherited from the spec; no task adds item handling.
- **Placeholder scan:** every code step has complete code. The "READ FIRST / match real names" notes are integration-matching for the two edit-in-place tasks (publish hook, watch loop) where exact insertion points depend on existing structure; the code to insert is fully shown.
- **Type consistency:** `mark_pending(spell_ids, *, reason, names=None, path=None)`, `load_pending(*, path=None)`, `clear_pending(*, path=None)`, `apply_pending_client_patch(*, install_path, mpq_editor, pending_path, build_fn, cache_clear_fn)`, `ClientPatchCloseWatcher(apply_fn=...).tick(running=...)`, `_note_client_patch_pending(*, spell_entry, mode, applied)`, `_wow_client_running()` — all defined before use and referenced consistently across tasks.
- **Build API correctness:** `build_client_patch_package` installs via `install_path` (no `install` bool) — the apply step passes `install_path`, and tests inject `build_fn` so the real signature is exercised only through `_default_build_fn`. Verify `default_*_path()` helper names during Task 2 (confirmed present: `default_source_dbc_path/default_package_path/default_mpq_editor_path/default_install_path`).
- **Assumption to verify (Task 4):** `draft.spell_entry` and `SpellPublishResult.applied` — confirmed used in publish.py; the helper is structured so the hook fires only on apply-success.
