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
        "config": {
            "llm_enabled": True,
            "llm_chat_enabled": True,
            "llm_lanes": ["chat", "scene", "action"],
            "llm_event_age_seconds": 300,
            "llm_cooldown_seconds": 60,
            "llm_events_per_tick": 1,
            "llm_chat_context_epoch": 0,
            "llm_chat_context_reset_at": None,
        },
        "policy": {},
        "latest_opportunity": None,
        "latest_proposal": None,
        "latest_dry_run": None,
        "latest_apply": None,
        "latest_rollback": None,
        "proposal_queue": [],
        "issues": [],
        "pending_intents": {},
        "maintenance_pending": [],
        "counters": {
            "ticks": 0,
            "drafts_generated": 0,
            "auto_applied": 0,
            "parked": 0,
            "maintenance_staged": 0,
        },
        "latest_chat": None,
        "latest_chat_context_reset": None,
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

    @property
    def seen_events_path(self) -> Path:
        return self.root / "seen_events.json"

    @property
    def idempotency_path(self) -> Path:
        return self.root / "idempotency.json"

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
        command = self.load_command()
        self.save_command({
            "stop_requested": True,
            "paused": status.get("paused", False),
            "config": command.get("config", status.get("config", {})),
        })
        return status

    def set_paused(self, paused: bool) -> dict[str, Any]:
        status = self.update_status(paused=bool(paused), status="paused" if paused else "running")
        command = self.load_command()
        self.save_command({
            "stop_requested": bool(status.get("stop_requested")),
            "paused": bool(paused),
            "config": command.get("config", status.get("config", {})),
        })
        return status

    def configure(self, config: dict[str, Any]) -> dict[str, Any]:
        status = self.load_status()
        current = dict(status.get("config") or {})
        normalized = {key: _normalize_config_value(key, value) for key, value in config.items() if value is not None}
        current.update(normalized)
        status["config"] = current
        saved = self.save_status(status)
        command = self.load_command()
        command["config"] = current
        command.setdefault("stop_requested", bool(saved.get("stop_requested")))
        command.setdefault("paused", bool(saved.get("paused")))
        self.save_command(command)
        return saved

    def reset_chat_context(self, *, actor_guid: int | None = None, source: str = "operator") -> dict[str, Any]:
        status = self.load_status()
        config = dict(status.get("config") or {})
        epoch = int(config.get("llm_chat_context_epoch") or 0) + 1
        reset_at = utc_now_iso()
        config["llm_chat_context_epoch"] = epoch
        config["llm_chat_context_reset_at"] = reset_at
        record = {
            "at": reset_at,
            "actor_guid": actor_guid,
            "source": str(source),
            "epoch": epoch,
        }
        status["config"] = config
        status["latest_chat"] = None
        status["latest_generation"] = None
        status["latest_chat_context_reset"] = record
        saved = self.save_status(status)
        command = self.load_command()
        command["config"] = {**dict(command.get("config") or {}), **config}
        command.setdefault("stop_requested", bool(saved.get("stop_requested")))
        command.setdefault("paused", bool(saved.get("paused")))
        self.save_command(command)
        self.append_journal("chat_context_reset", record)
        return saved

    def add_opportunity(self, opportunity: dict[str, Any]) -> dict[str, Any]:
        status = self.load_status()
        payload = {"at": utc_now_iso(), **opportunity}
        status["latest_opportunity"] = payload
        self.write_json(
            self.root / "opportunities" / f"{_safe_name(str(payload.get('opportunity_id') or payload['at']))}.json",
            payload,
        )
        self.save_status(status)
        self.append_journal("opportunity", payload)
        return payload

    def add_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        status = self.load_status()
        payload = {"at": utc_now_iso(), **draft}
        draft_id = str(payload.get("draft_id") or f"autoplay-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}")
        payload["draft_id"] = draft_id
        self.write_json(self.root / "drafts" / f"{_safe_name(draft_id)}.json", payload)
        queue = [payload, *list(status.get("proposal_queue") or [])][:50]
        status["latest_proposal"] = payload
        status["proposal_queue"] = queue
        counters = dict(status.get("counters") or {})
        counters["drafts_generated"] = int(counters.get("drafts_generated") or 0) + 1
        status["counters"] = counters
        self.save_status(status)
        self.append_journal("draft", payload)
        return payload

    def update_draft(self, draft_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        status = self.load_status()
        queue = list(status.get("proposal_queue") or [])
        found: dict[str, Any] | None = None
        next_queue: list[dict[str, Any]] = []
        for item in queue:
            if isinstance(item, dict) and str(item.get("draft_id") or "") == str(draft_id):
                found = {**item, **updates, "updated_at": utc_now_iso()}
                next_queue.append(found)
            else:
                next_queue.append(item)
        draft_path = self.root / "drafts" / f"{_safe_name(str(draft_id))}.json"
        if found is None and draft_path.exists():
            raw = self.read_json(draft_path)
            if isinstance(raw, dict):
                found = {**raw, **updates, "updated_at": utc_now_iso()}
        if found is None:
            return None
        self.write_json(draft_path, found)
        status["proposal_queue"] = next_queue
        if isinstance(status.get("latest_proposal"), dict) and str(status["latest_proposal"].get("draft_id") or "") == str(draft_id):
            status["latest_proposal"] = found
        if "latest_dry_run" in updates:
            status["latest_dry_run"] = updates["latest_dry_run"]
        if "latest_apply" in updates:
            status["latest_apply"] = updates["latest_apply"]
        if "counters" in updates and isinstance(updates["counters"], dict):
            status["counters"] = updates["counters"]
        self.save_status(status)
        self.append_journal("draft_update", {"draft_id": str(draft_id), "updates": updates})
        return found

    def load_seen_event_keys(self) -> set[str]:
        self.ensure()
        if not self.seen_events_path.exists():
            return set()
        raw = self.read_json(self.seen_events_path)
        if isinstance(raw, dict) and isinstance(raw.get("source_event_keys"), list):
            return {str(item) for item in raw["source_event_keys"]}
        return set()

    def mark_event_seen(self, source_event_key: str, *, limit: int = 500) -> list[str]:
        keys = [str(source_event_key), *[key for key in self.load_seen_event_keys() if key != str(source_event_key)]]
        keys = keys[:limit]
        self.write_json(
            self.seen_events_path,
            {
                "schema_version": "wm.autoplay.seen_events.v1",
                "updated_at": utc_now_iso(),
                "source_event_keys": keys,
            },
        )
        return keys

    def load_idempotency_keys(self) -> set[str]:
        self.ensure()
        if not self.idempotency_path.exists():
            return set()
        raw = self.read_json(self.idempotency_path)
        if isinstance(raw, dict) and isinstance(raw.get("keys"), list):
            return {str(item) for item in raw["keys"]}
        return set()

    def mark_idempotency_key(self, key: str, *, limit: int = 1000) -> list[str]:
        keys = [str(key), *[item for item in self.load_idempotency_keys() if item != str(key)]]
        keys = keys[:limit]
        self.write_json(
            self.idempotency_path,
            {
                "schema_version": "wm.autoplay.idempotency.v1",
                "updated_at": utc_now_iso(),
                "keys": keys,
            },
        )
        return keys

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

    def set_pending_intent(self, player_guid: int, record: dict[str, Any], *, ttl_seconds: int = 120) -> dict[str, Any]:
        from datetime import timedelta
        status = self.load_status()
        pending = dict(status.get("pending_intents") or {})
        created = datetime.now(timezone.utc).replace(microsecond=0)
        payload = {
            **record,
            "player_guid": int(player_guid),
            "created_at": created.isoformat().replace("+00:00", "Z"),
            "expires_at": (created + timedelta(seconds=int(ttl_seconds))).isoformat().replace("+00:00", "Z"),
        }
        pending[str(int(player_guid))] = payload
        status["pending_intents"] = pending
        self.save_status(status)
        self.append_journal("pending_intent_set", payload)
        return payload

    def load_pending_intent(self, player_guid: int) -> dict[str, Any] | None:
        status = self.load_status()
        pending = dict(status.get("pending_intents") or {})
        record = pending.get(str(int(player_guid)))
        if not isinstance(record, dict):
            return None
        expires = _parse_iso(record.get("expires_at"))
        if expires is None or datetime.now(timezone.utc) > expires:
            pending.pop(str(int(player_guid)), None)
            status["pending_intents"] = pending
            self.save_status(status)
            return None
        return record

    def clear_pending_intent(self, player_guid: int, *, reason: str = "cleared") -> None:
        status = self.load_status()
        pending = dict(status.get("pending_intents") or {})
        if pending.pop(str(int(player_guid)), None) is not None:
            status["pending_intents"] = pending
            self.save_status(status)
            self.append_journal("pending_intent_cleared", {"player_guid": int(player_guid), "reason": reason})

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


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)[:180]


def _normalize_config_value(key: str, value: Any) -> Any:
    if key == "llm_lanes":
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
    if key in {"llm_event_age_seconds", "llm_cooldown_seconds", "llm_events_per_tick", "llm_chat_context_epoch"}:
        return int(value)
    if key in {"llm_enabled", "llm_chat_enabled"}:
        return bool(value)
    return value
