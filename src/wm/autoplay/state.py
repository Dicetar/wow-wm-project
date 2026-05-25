from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


DEFAULT_AUTOPLAY_ROOT = Path(".wm-bootstrap/state/autoplay")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_status() -> dict[str, Any]:
    return {
        "schema_version": "wm.autoplay.status.v1",
        "status": "stopped",
        "running": False,
        "paused": False,
        "stop_requested": False,
        "updated_at": None,
        "pid": None,
        "active_session": None,
        "readiness": {"ok": False, "checks": [], "blockers": []},
        "llm": {"ok": False, "base_url": "http://localhost:1234/v1", "model": None, "models": [], "error": None},
        "policy": {},
        "latest_opportunity": None,
        "latest_proposal": None,
        "latest_dry_run": None,
        "latest_apply": None,
        "latest_rollback": None,
        "proposal_queue": [],
        "issues": [],
        "maintenance_pending": [],
        "counters": {
            "ticks": 0,
            "drafts_generated": 0,
            "auto_applied": 0,
            "parked": 0,
            "maintenance_staged": 0,
        },
    }


@dataclass(slots=True)
class AutoplayStateStore:
    root: Path = DEFAULT_AUTOPLAY_ROOT

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("drafts", "issues", "maintenance", "journal", "opportunities"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    @property
    def status_path(self) -> Path:
        return self.root / "status.json"

    @property
    def command_path(self) -> Path:
        return self.root / "command.json"

    def load_status(self) -> dict[str, Any]:
        self.ensure()
        status = default_status()
        if self.status_path.exists():
            raw = self.read_json(self.status_path)
            if isinstance(raw, dict):
                _deep_update(status, raw)
        return status

    def save_status(self, status: dict[str, Any]) -> dict[str, Any]:
        self.ensure()
        payload = dict(status)
        payload["updated_at"] = utc_now_iso()
        self.write_json(self.status_path, payload)
        return payload

    def update_status(self, **updates: Any) -> dict[str, Any]:
        status = self.load_status()
        status.update(updates)
        return self.save_status(status)

    def load_command(self) -> dict[str, Any]:
        self.ensure()
        if not self.command_path.exists():
            return {}
        raw = self.read_json(self.command_path)
        return raw if isinstance(raw, dict) else {}

    def save_command(self, command: dict[str, Any]) -> dict[str, Any]:
        self.ensure()
        payload = {**command, "updated_at": utc_now_iso()}
        self.write_json(self.command_path, payload)
        return payload

    def request_stop(self) -> dict[str, Any]:
        status = self.update_status(stop_requested=True, running=False, status="stopping")
        self.save_command({"stop_requested": True, "paused": status.get("paused", False)})
        return status

    def set_paused(self, paused: bool) -> dict[str, Any]:
        status = self.update_status(paused=bool(paused), status="paused" if paused else "running")
        self.save_command({"stop_requested": bool(status.get("stop_requested")), "paused": bool(paused)})
        return status

    def append_journal(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.ensure()
        entry = {"kind": kind, "at": utc_now_iso(), **payload}
        path = self.root / "journal" / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-{kind}.json"
        self.write_json(path, entry)
        return entry

    def add_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        status = self.load_status()
        payload = {"at": utc_now_iso(), **issue}
        issues = [payload, *list(status.get("issues") or [])][:50]
        status["issues"] = issues
        counters = dict(status.get("counters") or {})
        counters["parked"] = int(counters.get("parked") or 0) + 1
        status["counters"] = counters
        self.save_status(status)
        self.append_journal("issue", payload)
        return payload

    def add_maintenance(self, item: dict[str, Any]) -> dict[str, Any]:
        status = self.load_status()
        payload = {"at": utc_now_iso(), **item}
        pending = [payload, *list(status.get("maintenance_pending") or [])][:50]
        status["maintenance_pending"] = pending
        counters = dict(status.get("counters") or {})
        counters["maintenance_staged"] = int(counters.get("maintenance_staged") or 0) + 1
        status["counters"] = counters
        self.save_status(status)
        self.append_journal("maintenance", payload)
        return payload

    @staticmethod
    def read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)


def _deep_update(base: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
