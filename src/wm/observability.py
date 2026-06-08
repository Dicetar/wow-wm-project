from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


PROOF_KINDS = {
    "runtime_startup": ["Start launcher/core", "Verify one logical instance per service", "Record runtime status"],
    "chat_action": ["Send WM chat line", "Compile typed intent", "Apply or block", "Verify native result"],
    "scene": ["Compose scene", "Run native action sequence", "Verify cleanup"],
    "ambient": ["Trigger notable event", "Verify rate-limited narration"],
    "memory": ["State durable preference", "Persist steering note", "Verify later context use"],
    "content": ["Generate packet", "Dry-run release", "Stage/apply only through safe gates"],
    "rollback": ["Apply reversible artifact", "Run rollback", "Verify cleanup"],
    "failure": ["Force dependency failure", "Verify actionable incident"],
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class WmObservabilityStore:
    root: Path
    autoplay_root: Path | None = None

    @classmethod
    def for_project(cls, project_root: str | Path) -> "WmObservabilityStore":
        root = Path(project_root)
        return cls(
            root=root / ".wm-bootstrap" / "state" / "observability",
            autoplay_root=root / ".wm-bootstrap" / "state" / "autoplay",
        )

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("proofs", "incidents"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def list_proofs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._list_dir("proofs", limit=limit)

    def latest_proofs_by_kind(self, *, limit: int = 200) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for proof in self.list_proofs(limit=limit):
            kind = str(proof.get("proof_kind") or "")
            if kind and kind not in latest:
                latest[kind] = proof
        return latest

    def list_autoplay_journal(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._autoplay_journal(limit=limit)

    def record_proof(self, *, proof_kind: str, mode: str = "dry-run", player_guid: int | None = None) -> dict[str, Any]:
        self.ensure()
        kind = proof_kind if proof_kind in PROOF_KINDS else "custom"
        now = utc_now_iso()
        record = {
            "schema_version": "wm.proof.record.v1",
            "proof_id": f"proof-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            "proof_kind": str(proof_kind),
            "known_kind": proof_kind in PROOF_KINDS,
            "mode": str(mode or "dry-run"),
            "status": "planned" if str(mode or "dry-run") == "dry-run" else "manual_required",
            "player_guid": player_guid,
            "created_at": now,
            "steps": PROOF_KINDS.get(kind, ["Run operator-defined proof packet"]),
            "evidence": [],
        }
        return self.save_proof(record)

    def save_proof(self, record: dict[str, Any]) -> dict[str, Any]:
        self.ensure()
        proof_id = str(record.get("proof_id") or f"proof-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}")
        payload = {**record, "proof_id": proof_id}
        self._write_record("proofs", proof_id, payload)
        return payload

    def list_incidents(self, *, limit: int = 50, runtime_status: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        recorded = self._list_dir("incidents", limit=limit)
        synthetic = []
        for item in (runtime_status or {}).get("incidents") or []:
            if isinstance(item, dict):
                synthetic.append({"source": "runtime", **item})
        return (synthetic + recorded)[:limit]

    def record_incident(self, *, kind: str, message: str, severity: str = "warning", service: str | None = None) -> dict[str, Any]:
        self.ensure()
        now = utc_now_iso()
        record = {
            "schema_version": "wm.incident.v1",
            "incident_id": f"incident-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            "kind": str(kind),
            "severity": str(severity or "warning"),
            "service": service,
            "message": str(message),
            "created_at": now,
        }
        self._write_record("incidents", record["incident_id"], record)
        return record

    def list_timeline(self, *, limit: int = 100, runtime_status: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for proof in self.list_proofs(limit=limit):
            items.append(_timeline_item(at=proof.get("created_at"), kind="proof", payload=proof))
        for incident in self.list_incidents(limit=limit, runtime_status=runtime_status):
            items.append(_timeline_item(
                at=incident.get("created_at") or incident.get("at"),
                kind="incident",
                payload=incident,
            ))
        for entry in self._autoplay_journal(limit=limit):
            items.append(_timeline_item(
                at=entry.get("at"),
                kind=f"autoplay.{entry.get('kind', 'event')}",
                payload=entry,
            ))
        items.sort(key=lambda item: str(item.get("at") or ""), reverse=True)
        return items[:limit]

    def _autoplay_journal(self, *, limit: int) -> list[dict[str, Any]]:
        if self.autoplay_root is None:
            return []
        journal = self.autoplay_root / "journal"
        if not journal.exists():
            return []
        items: list[dict[str, Any]] = []
        for path in sorted(journal.glob("*.json"), reverse=True):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(raw, dict):
                items.append(raw)
            if len(items) >= limit:
                break
        return items

    def _list_dir(self, name: str, *, limit: int) -> list[dict[str, Any]]:
        self.ensure()
        items: list[dict[str, Any]] = []
        for path in sorted((self.root / name).glob("*.json"), reverse=True):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(raw, dict):
                items.append(raw)
            if len(items) >= limit:
                break
        return items

    def _write_record(self, directory: str, record_id: str, payload: dict[str, Any]) -> None:
        self.ensure()
        path = self.root / directory / f"{_safe_name(record_id)}.json"
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value))[:120]


def _timeline_item(*, at: Any, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "at": at,
        "kind": kind,
        "summary": _timeline_summary(kind=kind, payload=payload),
        "payload": payload,
    }


def _timeline_summary(*, kind: str, payload: dict[str, Any]) -> str:
    if kind == "proof":
        proof_kind = payload.get("proof_kind") or payload.get("title") or "proof"
        status = payload.get("status") or "unknown"
        return _short(f"Proof {proof_kind}: {status}")
    if kind == "incident":
        service = payload.get("service") or payload.get("kind") or "incident"
        message = payload.get("message") or payload.get("detail") or payload.get("severity") or "recorded"
        return _short(f"{service}: {message}")

    entry_kind = str(payload.get("kind") or kind.removeprefix("autoplay."))
    if entry_kind == "chat":
        message = _nested_text(payload, "reply", "message") or payload.get("message") or payload.get("player_message")
        return _short(f"Chat: {message or 'turn recorded'}")
    if entry_kind == "ambient_narration":
        return _short(f"Ambient: {payload.get('line') or payload.get('message') or 'narration recorded'}")
    if entry_kind == "conversation_memory":
        note = payload.get("note") if isinstance(payload.get("note"), dict) else {}
        return _short(f"Memory: {note.get('summary') or note.get('value') or payload.get('summary') or 'stored'}")
    if entry_kind == "deed":
        return _short(f"Deed: {payload.get('action_kind') or payload.get('native_action_kind') or payload.get('status') or 'recorded'}")
    if entry_kind == "scene_run":
        return _short(f"Scene: {payload.get('scene_key') or payload.get('status') or 'run recorded'}")
    if entry_kind == "issue":
        return _short(f"Issue: {payload.get('reason') or payload.get('detail') or 'recorded'}")
    if entry_kind.startswith("pending_intent"):
        return _short(f"Intent: {payload.get('native_action_kind') or payload.get('reason') or entry_kind}")
    if entry_kind.startswith("autoplay_"):
        return _short(f"Autoplay: {payload.get('status') or payload.get('draft_id') or entry_kind}")
    return _short(f"{entry_kind}: recorded")


def _nested_text(raw: dict[str, Any], *keys: str) -> str | None:
    current: Any = raw
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current in (None, ""):
        return None
    return str(current)


def _short(value: Any, *, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."
