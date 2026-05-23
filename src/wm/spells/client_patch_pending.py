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
