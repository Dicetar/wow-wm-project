from __future__ import annotations

from datetime import datetime
from datetime import timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


MARKER_SCHEMA_VERSION = "wm.runtime.marker.v1"
DEFAULT_MARKER_STALE_SECONDS = 30
DEFAULT_MARKER_RELATIVE_ROOT = Path(".wm-bootstrap") / "state" / "runtime"
STOPPED_HEALTH = {"stopped", "not_running", "exited"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_runtime_marker_root(project_root: str | Path | None = None) -> Path:
    configured = os.getenv("WM_RUNTIME_MARKER_ROOT")
    if configured not in (None, ""):
        return Path(str(configured)).resolve()
    root = Path(project_root or Path.cwd()).resolve()
    return root / DEFAULT_MARKER_RELATIVE_ROOT


def write_runtime_marker(
    *,
    service: str,
    command_key: str,
    project_root: str | Path | None = None,
    root: str | Path | None = None,
    pid: int | None = None,
    health: str = "running",
    port: int | None = None,
    metadata: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    marker_root = Path(root).resolve() if root is not None else default_runtime_marker_root(project_root)
    process_id = int(pid if pid is not None else os.getpid())
    path = _marker_path(marker_root, service=service, pid=process_id)
    seen_at = now or utc_now_iso()
    started_at = seen_at
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, dict) and existing.get("started_at") not in (None, ""):
            started_at = str(existing["started_at"])
    except (OSError, ValueError):
        pass
    payload = {
        "schema_version": MARKER_SCHEMA_VERSION,
        "service": str(service),
        "pid": process_id,
        "started_at": started_at,
        "last_seen": seen_at,
        "command_key": str(command_key),
        "command_hash": _command_hash([str(command_key)]),
        "health": str(health or "running"),
        "port": int(port) if port is not None else None,
        "metadata": dict(metadata or {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return normalize_runtime_marker(payload, now=seen_at)


def mark_runtime_service_stopped(
    *,
    service: str,
    command_key: str,
    project_root: str | Path | None = None,
    root: str | Path | None = None,
    pid: int | None = None,
    port: int | None = None,
    metadata: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    return write_runtime_marker(
        service=service,
        command_key=command_key,
        project_root=project_root,
        root=root,
        pid=pid,
        port=port,
        health="stopped",
        metadata=metadata,
        now=now,
    )


def load_runtime_markers(
    *,
    project_root: str | Path | None = None,
    root: str | Path | None = None,
    now: str | None = None,
    stale_after_seconds: int = DEFAULT_MARKER_STALE_SECONDS,
) -> list[dict[str, Any]]:
    marker_root = Path(root).resolve() if root is not None else default_runtime_marker_root(project_root)
    if not marker_root.exists():
        return []
    markers: list[dict[str, Any]] = []
    for path in sorted(marker_root.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        if raw.get("schema_version") != MARKER_SCHEMA_VERSION:
            continue
        marker = normalize_runtime_marker(raw, now=now, stale_after_seconds=stale_after_seconds)
        marker["path"] = str(path)
        markers.append(marker)
    return markers


def clear_runtime_markers(
    *,
    project_root: str | Path | None = None,
    root: str | Path | None = None,
    services: Iterable[str] | None = None,
) -> int:
    marker_root = Path(root).resolve() if root is not None else default_runtime_marker_root(project_root)
    if not marker_root.exists():
        return 0
    service_filter = {str(item) for item in services} if services is not None else None
    removed = 0
    for path in sorted(marker_root.glob("*.json")):
        service = None
        if service_filter is not None:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = {}
            if isinstance(raw, dict):
                service = str(raw.get("service") or "")
            if service not in service_filter:
                continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def normalize_runtime_marker(
    raw: dict[str, Any],
    *,
    now: str | None = None,
    stale_after_seconds: int = DEFAULT_MARKER_STALE_SECONDS,
) -> dict[str, Any]:
    generated = now or utc_now_iso()
    health = str(raw.get("health") or "running").lower()
    last_seen = str(raw.get("last_seen") or "")
    age_seconds = _age_seconds(last_seen, generated)
    stale = health not in STOPPED_HEALTH and (age_seconds is None or age_seconds > int(stale_after_seconds))
    payload = dict(raw)
    payload["schema_version"] = str(raw.get("schema_version") or MARKER_SCHEMA_VERSION)
    payload["service"] = str(raw.get("service") or "")
    payload["pid"] = _int_or_none(raw.get("pid"))
    payload["started_at"] = str(raw.get("started_at") or "") or None
    payload["last_seen"] = last_seen or None
    payload["command_key"] = str(raw.get("command_key") or "")
    payload["command_hash"] = str(raw.get("command_hash") or _command_hash([payload["command_key"]]) or "")
    payload["health"] = health
    payload["port"] = _int_or_none(raw.get("port"))
    payload["metadata"] = dict(raw.get("metadata") or {}) if isinstance(raw.get("metadata"), dict) else {}
    payload["age_seconds"] = age_seconds
    payload["stale"] = stale
    payload["active"] = health not in STOPPED_HEALTH and not stale
    return payload


def _marker_path(root: Path, *, service: str, pid: int) -> Path:
    return root / f"{_safe_name(service)}-{int(pid)}.json"


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value))[:80]


def _command_hash(commands: list[str]) -> str | None:
    values = [item for item in commands if item]
    if not values:
        return None
    normalized = "\n".join(sorted(" ".join(command.split()) for command in values))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _age_seconds(seen_at: str, now: str) -> float | None:
    seen = _parse_iso(seen_at)
    generated = _parse_iso(now)
    if seen is None or generated is None:
        return None
    return max((generated - seen).total_seconds(), 0.0)


def _parse_iso(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
