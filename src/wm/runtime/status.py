from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Iterable

from wm.runtime.markers import DEFAULT_MARKER_STALE_SECONDS
from wm.runtime.markers import load_runtime_markers
from wm.runtime.markers import normalize_runtime_marker
from wm.runtime.markers import STOPPED_HEALTH


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class RuntimeProcess:
    pid: int
    parent_pid: int | None
    name: str
    command_line: str
    started_at: str | None = None
    window_title: str = ""

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "RuntimeProcess":
        pid = _int_or_zero(raw.get("pid", raw.get("ProcessId")))
        parent = raw.get("parent_pid", raw.get("ParentProcessId"))
        return cls(
            pid=pid,
            parent_pid=_int_or_none(parent),
            name=str(raw.get("name", raw.get("Name", "")) or ""),
            command_line=str(raw.get("command_line", raw.get("CommandLine", "")) or ""),
            started_at=_started_at(raw.get("started_at", raw.get("CreationDate"))),
            window_title=str(raw.get("window_title", raw.get("MainWindowTitle", "")) or ""),
        )


@dataclass(frozen=True, slots=True)
class RuntimeServiceSpec:
    key: str
    label: str
    names: tuple[str, ...] = ()
    command_terms: tuple[str, ...] = ()
    title_terms: tuple[str, ...] = ()
    required: bool = False


def default_service_specs() -> tuple[RuntimeServiceSpec, ...]:
    return (
        RuntimeServiceSpec("db", "BridgeLab MySQL", names=("mysqld.exe",)),
        RuntimeServiceSpec("auth", "Auth Server", names=("authserver.exe",)),
        RuntimeServiceSpec("world", "World Server", names=("worldserver.exe",)),
        RuntimeServiceSpec("watcher", "Native Watcher", command_terms=("wm.events.watch", "native_bridge"), title_terms=("WM Native Watcher",)),
        RuntimeServiceSpec("autoplay", "Autoplay", command_terms=("wm.autoplay", "run"), title_terms=("WM Autoplay",)),
        RuntimeServiceSpec("panel", "Panel Server", command_terms=("wm.panel", "serve"), title_terms=("WM Panel Server",)),
    )


def collect_runtime_status(
    *,
    project_root: str | Path | None = None,
    db_port: int = 33307,
    soap_port: int = 7879,
    panel_host: str = "127.0.0.1",
    panel_port: int = 8765,
    processes: Iterable[RuntimeProcess | dict[str, Any]] | None = None,
    autoplay_status: dict[str, Any] | None = None,
    runtime_markers: Iterable[dict[str, Any]] | None = None,
    marker_stale_after_seconds: int = DEFAULT_MARKER_STALE_SECONDS,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return the shared local runtime view used by launcher, panel, and CLI.

    The scanner deliberately reports logical service roots instead of raw OS
    processes. Windows venv shims often create parent/child pairs for one
    visible service window; counting roots keeps the UI from reporting fake
    duplicates.
    """
    root = Path(project_root or Path.cwd()).resolve()
    generated = generated_at or utc_now_iso()
    scan_error: str | None = None
    if processes is None:
        processes_list, scan_error = _scan_windows_processes()
    else:
        processes_list = [
            item if isinstance(item, RuntimeProcess) else RuntimeProcess.from_mapping(item)
            for item in processes
        ]
    services = {
        spec.key: _service_status(spec, processes_list, generated_at=generated)
        for spec in default_service_specs()
    }

    markers = _load_or_normalize_markers(
        root=root,
        runtime_markers=runtime_markers,
        generated_at=generated,
        stale_after_seconds=marker_stale_after_seconds,
    )
    _apply_runtime_markers(services, markers)

    durable_autoplay = autoplay_status if autoplay_status is not None else _load_autoplay_status(root)
    _apply_autoplay_staleness(services["autoplay"], durable_autoplay)

    incidents = _runtime_incidents(services)
    if scan_error:
        incidents.insert(0, {
            "kind": "process_scan_failed",
            "severity": "warning",
            "service": "runtime",
            "message": scan_error,
            "at": generated,
        })

    return {
        "schema_version": "wm.runtime.status.v1",
        "generated_at": generated,
        "project_root": str(root),
        "ok": not any(item["severity"] == "error" for item in incidents),
        "port_profile": {
            "db": {"host": "127.0.0.1", "port": int(db_port)},
            "soap": {"host": "127.0.0.1", "port": int(soap_port), "enabled": True},
            "panel": {"host": str(panel_host), "port": int(panel_port)},
        },
        "process_scan_error": scan_error,
        "runtime_markers": {
            "root": str(root / ".wm-bootstrap" / "state" / "runtime"),
            "stale_after_seconds": int(marker_stale_after_seconds),
            "count": len(markers),
        },
        "services": services,
        "summary": {
            key: {
                "state": svc["state"],
                "health": svc["health"],
                "logical_count": svc["logical_count"],
                "stale": svc["stale"],
            }
            for key, svc in services.items()
        },
        "incidents": incidents,
    }


def _service_status(spec: RuntimeServiceSpec, processes: list[RuntimeProcess], *, generated_at: str) -> dict[str, Any]:
    matched = [proc for proc in processes if _matches(spec, proc)]
    matched_ids = {proc.pid for proc in matched if proc.pid}
    roots = [proc for proc in matched if proc.parent_pid not in matched_ids]
    children_by_parent: dict[int, list[int]] = {}
    for proc in matched:
        if proc.parent_pid in matched_ids:
            children_by_parent.setdefault(int(proc.parent_pid), []).append(proc.pid)
    if spec.key == "db" and len(matched) == 2 and all(proc.parent_pid is None for proc in matched):
        # BridgeLab/MySQL commonly appears as a launcher/worker pair. The
        # limited Get-Process fallback cannot see the parent PID, so collapse the
        # two mysqld processes into one logical service instead of reporting a
        # false duplicate.
        roots = [matched[0]]
        children_by_parent = {matched[0].pid: [matched[1].pid]}
    logical_count = len(roots)
    state = "not_running"
    health = "not_running"
    if logical_count == 1:
        state = "running"
        health = "running"
    elif logical_count > 1:
        state = "duplicate"
        health = "duplicate"
    root_commands = [root.command_line for root in roots if root.command_line]
    return {
        "service": spec.key,
        "label": spec.label,
        "state": state,
        "health": health,
        "stale": False,
        "logical_count": logical_count,
        "process_count": len(matched),
        "pid_tree": [
            {
                "pid": root.pid,
                "child_pids": sorted(children_by_parent.get(root.pid, [])),
                "name": root.name,
                "started_at": root.started_at,
            }
            for root in roots
        ],
        "pids": sorted(matched_ids),
        "command_hash": _command_hash(root_commands),
        "started_at": min((root.started_at for root in roots if root.started_at), default=None),
        "last_seen": generated_at if matched else None,
        "match": {"names": list(spec.names), "command_terms": list(spec.command_terms), "title_terms": list(spec.title_terms)},
    }


def _load_or_normalize_markers(
    *,
    root: Path,
    runtime_markers: Iterable[dict[str, Any]] | None,
    generated_at: str,
    stale_after_seconds: int,
) -> list[dict[str, Any]]:
    if runtime_markers is None:
        return load_runtime_markers(
            project_root=root,
            now=generated_at,
            stale_after_seconds=stale_after_seconds,
        )
    return [
        normalize_runtime_marker(
            dict(item),
            now=generated_at,
            stale_after_seconds=stale_after_seconds,
        )
        for item in runtime_markers
        if isinstance(item, dict)
    ]


def _apply_runtime_markers(services: dict[str, dict[str, Any]], markers: list[dict[str, Any]]) -> None:
    marker_services = {"watcher", "panel", "autoplay"}
    for key in marker_services:
        service = services.get(key)
        if service is None:
            continue
        relevant = [marker for marker in markers if marker.get("service") == key]
        if not relevant:
            service["runtime_markers"] = {"available": False, "active_count": 0, "stale_count": 0, "stopped_count": 0}
            continue
        active = [marker for marker in relevant if bool(marker.get("active"))]
        stale = [
            marker
            for marker in relevant
            if str(marker.get("health") or "") not in STOPPED_HEALTH and bool(marker.get("stale"))
        ]
        stopped = [marker for marker in relevant if str(marker.get("health") or "") in STOPPED_HEALTH]
        service["runtime_markers"] = {
            "available": True,
            "active_count": len(active),
            "stale_count": len(stale),
            "stopped_count": len(stopped),
            "markers": [_marker_public(marker) for marker in relevant],
        }
        if active:
            _replace_service_with_markers(service, active, state="running" if len(active) == 1 else "duplicate")
        elif stale:
            _replace_service_with_markers(service, stale, state="stale")
        elif int(service.get("logical_count") or 0) <= 0:
            service["state"] = "not_running"
            service["health"] = "not_running"
            service["stale"] = False
            service["last_seen"] = None


def _replace_service_with_markers(service: dict[str, Any], markers: list[dict[str, Any]], *, state: str) -> None:
    pids = sorted(int(marker["pid"]) for marker in markers if marker.get("pid") is not None)
    commands = [str(marker.get("command_key") or "") for marker in markers if marker.get("command_key")]
    previous_process_count = int(service.get("process_count") or 0)
    service["state"] = state
    service["health"] = "stale" if state == "stale" else state
    service["stale"] = state == "stale"
    service["logical_count"] = len(markers)
    service["process_count"] = max(previous_process_count, len(markers))
    service["pid_tree"] = [
        {
            "pid": marker.get("pid"),
            "child_pids": [],
            "name": "runtime_marker",
            "started_at": marker.get("started_at"),
        }
        for marker in markers
    ]
    service["pids"] = pids
    service["command_hash"] = _command_hash(commands)
    service["started_at"] = min((str(marker.get("started_at")) for marker in markers if marker.get("started_at")), default=None)
    service["last_seen"] = max((str(marker.get("last_seen")) for marker in markers if marker.get("last_seen")), default=None)


def _marker_public(marker: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": marker.get("service"),
        "pid": marker.get("pid"),
        "started_at": marker.get("started_at"),
        "last_seen": marker.get("last_seen"),
        "command_key": marker.get("command_key"),
        "command_hash": marker.get("command_hash"),
        "health": marker.get("health"),
        "port": marker.get("port"),
        "age_seconds": marker.get("age_seconds"),
        "stale": bool(marker.get("stale")),
        "active": bool(marker.get("active")),
    }


def _matches(spec: RuntimeServiceSpec, proc: RuntimeProcess) -> bool:
    name = _normalize_process_name(proc.name)
    names = {_normalize_process_name(item) for item in spec.names}
    if name and name in names:
        return True
    if not spec.command_terms:
        if not spec.title_terms:
            return False
        title = proc.window_title.lower()
        return bool(title) and all(term.lower() in title for term in spec.title_terms)
    command = proc.command_line.lower()
    if command and all(term.lower() in command for term in spec.command_terms):
        return True
    if spec.title_terms:
        title = proc.window_title.lower()
        return bool(title) and all(term.lower() in title for term in spec.title_terms)
    return False


def _apply_autoplay_staleness(service: dict[str, Any], durable: dict[str, Any] | None) -> None:
    if not durable:
        service["durable"] = {"available": False}
        return
    durable_status = str(durable.get("status") or "")
    durable_running = bool(durable.get("running")) or durable_status in {"running", "paused"}
    live_running = int(service.get("logical_count") or 0) > 0
    service["durable"] = {
        "available": True,
        "status": durable_status or durable.get("status"),
        "running": bool(durable.get("running")),
        "paused": bool(durable.get("paused")),
        "updated_at": durable.get("updated_at"),
    }
    if durable_status == "stopping":
        if live_running:
            service["health"] = "stopping"
        return
    stale = durable_running != live_running
    if stale:
        service["stale"] = True
        service["health"] = "stale"


def _runtime_incidents(services: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    now = utc_now_iso()
    incidents: list[dict[str, Any]] = []
    for key, svc in services.items():
        if svc.get("state") == "duplicate":
            incidents.append({
                "kind": "duplicate_service",
                "severity": "error",
                "service": key,
                "message": f"{svc.get('label', key)} has {svc.get('logical_count')} logical instances.",
                "at": now,
            })
        if svc.get("stale"):
            markers = svc.get("runtime_markers") if isinstance(svc.get("runtime_markers"), dict) else {}
            source = "runtime marker heartbeat" if int(markers.get("stale_count") or 0) > 0 else "durable state"
            incidents.append({
                "kind": "stale_service_state",
                "severity": "warning",
                "service": key,
                "message": f"{svc.get('label', key)} {source} is stale.",
                "at": now,
            })
    return incidents


def _scan_windows_processes() -> tuple[list[RuntimeProcess], str | None]:
    if os.name != "nt":
        return [], "process scanning is only implemented for Windows hosts"
    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine,CreationDate | "
        "ConvertTo-Json -Depth 3"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
    except Exception as exc:
        return [], str(exc)
    if result.returncode != 0:
        fallback, fallback_error = _scan_get_process_fallback()
        detail = (result.stderr or result.stdout or f"powershell exit {result.returncode}").strip()
        if fallback_error:
            return [], f"{detail}; fallback failed: {fallback_error}"
        return fallback, f"{detail}; using limited Get-Process fallback"
    try:
        raw = json.loads(result.stdout or "[]")
    except ValueError as exc:
        return [], f"invalid process JSON: {exc}"
    if isinstance(raw, dict):
        raw_items = [raw]
    elif isinstance(raw, list):
        raw_items = raw
    else:
        raw_items = []
    return [RuntimeProcess.from_mapping(item) for item in raw_items if isinstance(item, dict)], None


def _scan_get_process_fallback() -> tuple[list[RuntimeProcess], str | None]:
    script = (
        "Get-Process | Select-Object "
        "@{Name='ProcessId';Expression={$_.Id}},"
        "@{Name='ParentProcessId';Expression={$null}},"
        "@{Name='Name';Expression={$_.ProcessName + '.exe'}},"
        "@{Name='CommandLine';Expression={''}},"
        "@{Name='MainWindowTitle';Expression={$_.MainWindowTitle}},"
        "@{Name='CreationDate';Expression={try {$_.StartTime.ToString('o')} catch {$null}}} | "
        "ConvertTo-Json -Depth 3"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
    except Exception as exc:
        return [], str(exc)
    if result.returncode != 0:
        return [], (result.stderr or result.stdout or f"powershell exit {result.returncode}").strip()
    try:
        raw = json.loads(result.stdout or "[]")
    except ValueError as exc:
        return [], f"invalid fallback process JSON: {exc}"
    if isinstance(raw, dict):
        raw_items = [raw]
    elif isinstance(raw, list):
        raw_items = raw
    else:
        raw_items = []
    return [RuntimeProcess.from_mapping(item) for item in raw_items if isinstance(item, dict)], None


def _load_autoplay_status(project_root: Path) -> dict[str, Any] | None:
    path = project_root / ".wm-bootstrap" / "state" / "autoplay" / "status.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _command_hash(commands: list[str]) -> str | None:
    if not commands:
        return None
    normalized = "\n".join(sorted(" ".join(command.split()) for command in commands))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _normalize_process_name(value: str) -> str:
    text = str(value or "").lower()
    return text[:-4] if text.endswith(".exe") else text


def _started_at(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.startswith("/Date("):
        return text
    return text


def _int_or_zero(value: Any) -> int:
    parsed = _int_or_none(value)
    return int(parsed or 0)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
