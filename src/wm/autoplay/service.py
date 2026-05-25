from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from wm.autoplay.llm import AutoplayLlmAdapter
from wm.autoplay.policy import AutoplayPolicy
from wm.autoplay.policy import SafeWindow
from wm.autoplay.policy import SCHEMA_LANE
from wm.autoplay.state import AutoplayStateStore
from wm.config import Settings
from wm.doctor import run_doctor
from wm.llm.lmstudio import LmStudioClient
from wm.llm.lmstudio import LmStudioSettings
from wm.panel.state import PanelState


DoctorFn = Callable[[Settings], list[Any]]


@dataclass(slots=True)
class AutoplayRuntimeConfig:
    player_guid: int | None = None
    interval_seconds: float = 2.0
    start_watcher: bool = True
    bridge_lab_mysql_port: int = 33307
    soap_port: int = 7879
    project_root: Path = Path.cwd()


class AutoplayService:
    def __init__(
        self,
        *,
        store: AutoplayStateStore | None = None,
        panel_state: PanelState | None = None,
        policy: AutoplayPolicy | None = None,
        doctor_fn: DoctorFn = run_doctor,
    ) -> None:
        self.store = store or AutoplayStateStore()
        self.panel_state = panel_state or PanelState()
        self.policy = policy or AutoplayPolicy()
        self.doctor_fn = doctor_fn

    def tick(self, *, config: AutoplayRuntimeConfig) -> dict[str, Any]:
        command = self.store.load_command()
        status = self.store.load_status()
        counters = dict(status.get("counters") or {})
        counters["ticks"] = int(counters.get("ticks") or 0) + 1

        stop_requested = bool(command.get("stop_requested") or status.get("stop_requested"))
        paused = bool(command.get("paused") or status.get("paused"))
        settings = Settings.from_env()
        readiness = self._readiness(settings)
        session = self._active_session(config=config)
        llm = self._llm_health()
        safe_window = self._safe_window(session=session)

        next_status = {
            **status,
            "status": "stopping" if stop_requested else "paused" if paused else "running",
            "running": not stop_requested,
            "paused": paused,
            "stop_requested": stop_requested,
            "pid": os.getpid(),
            "active_session": session,
            "readiness": readiness,
            "llm": llm,
            "policy": self.policy.to_dict(),
            "safe_window": safe_window.to_dict(),
            "counters": counters,
        }
        return self.store.save_status(next_status)

    def run_forever(self, *, config: AutoplayRuntimeConfig, once: bool = False) -> int:
        self.store.update_status(status="starting", running=True, paused=False, stop_requested=False, pid=os.getpid())
        if config.start_watcher and config.player_guid is not None:
            self._start_watcher(config)
        while True:
            status = self.tick(config=config)
            if once or status.get("stop_requested"):
                break
            time.sleep(max(float(config.interval_seconds), 0.25))
        final_status = "stopped" if once or status.get("stop_requested") else status.get("status", "stopped")
        self.store.update_status(status=final_status, running=False)
        return 0

    def _readiness(self, settings: Settings) -> dict[str, Any]:
        try:
            checks = self.doctor_fn(settings)
            blockers = [
                {"check": check.name, "status": check.status, "detail": check.detail}
                for check in checks
                if check.status != "WORKING"
            ]
            return {
                "ok": not blockers,
                "checks": [check.to_dict() for check in checks],
                "blockers": blockers,
            }
        except Exception as exc:
            return {
                "ok": False,
                "checks": [],
                "blockers": [{"check": "doctor", "status": "FAIL", "detail": str(exc)}],
            }

    def _active_session(self, *, config: AutoplayRuntimeConfig) -> dict[str, Any] | None:
        if config.player_guid is not None:
            return {
                "character_guid": int(config.player_guid),
                "source": "autoplay_arg",
            }
        session = self.panel_state.load_session()
        if session and session.get("character_guid") not in (None, ""):
            return session
        return None

    def _llm_health(self) -> dict[str, Any]:
        saved = self.panel_state.load_settings()
        if not saved.get("model"):
            saved = {**saved, "model": "qwen3-coder-30b-a3b-instruct"}
        adapter = AutoplayLlmAdapter(client=LmStudioClient(LmStudioSettings.from_dict(saved)))
        return adapter.health()

    def _safe_window(self, *, session: dict[str, Any] | None) -> SafeWindow:
        return SafeWindow(
            client_running=_wow_client_running(),
            scoped_player_online=_is_scoped_player_online(session),
        )

    def _start_watcher(self, config: AutoplayRuntimeConfig) -> None:
        script = config.project_root / "scripts" / "bridge_lab" / "Start-BridgeLabAutoBounty.ps1"
        if not script.exists():
            self.store.add_issue({"reason": f"watcher_start_missing_script:{script}", "kind": "watcher"})
            return
        args = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-WorkspaceRoot",
            str(config.project_root),
            "-PlayerGuid",
            str(config.player_guid),
            "-Mode",
            "apply",
            "-LabMySqlPort",
            str(config.bridge_lab_mysql_port),
            "-SoapPort",
            str(config.soap_port),
        ]
        completed = subprocess.run(args, capture_output=True, text=True, check=False)
        self.store.append_journal(
            "watcher_start",
            {
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )
        if completed.returncode != 0:
            self.store.add_issue({"reason": "watcher_start_failed", "kind": "watcher", "detail": completed.stderr[-1000:]})


def drive_pending_runtime(
    *,
    runtime: Any,
    store: AutoplayStateStore,
    policy: AutoplayPolicy,
    readiness_ok: bool,
    lm_ok: bool,
    safe_window: SafeWindow,
    lane_counts: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Auto-dry-run and apply eligible proposals from an existing SliceRuntime.

    This is deliberately separate from the service loop so tests and the panel
    can inject an in-process runtime without forcing live DB setup.
    """
    results: list[dict[str, Any]] = []
    lane_counts = dict(lane_counts or {})
    pending = list(runtime.gate.pending())
    for pp in pending:
        proposal = pp.proposal
        schema_version = _schema_from_proposal(proposal)
        lane = SCHEMA_LANE.get(schema_version, getattr(proposal.kind, "value", "unknown"))
        dry_run = _dry_run_pending(runtime.gate, int(pp.id))
        dry_run_ok = bool(getattr(dry_run, "ok", False))
        decision = policy.decide(
            schema_version=schema_version,
            payload=getattr(proposal, "payload", {}) or {},
            lane=lane,
            risk=_risk_from_proposal(proposal),
            readiness_ok=readiness_ok,
            lm_ok=lm_ok,
            session_ok=bool(getattr(proposal, "character_guid", 0)),
            source_event_at=_source_event_at(proposal),
            dry_run_ok=dry_run_ok,
            rollback_available=_rollback_available(runtime.gate, lane),
            idempotency_seen=False,
            lane_applied_count=int(lane_counts.get(lane, 0)),
            safe_window=safe_window,
        )
        record = {
            "proposal_id": int(pp.id),
            "kind": getattr(proposal.kind, "value", "unknown"),
            "lane": lane,
            "schema_version": schema_version,
            "dry_run": _result_to_dict(dry_run),
            "policy": decision.to_dict(),
        }
        if not dry_run_ok:
            issue = store.add_issue({"reason": "dry_run_failed", "kind": lane, "payload": dict(record)})
            record["issue"] = _compact_store_result(issue)
        elif decision.status == "maintenance_pending":
            maintenance = store.add_maintenance({
                "reason": ",".join(decision.maintenance_reasons),
                "kind": lane,
                "payload": dict(record),
            })
            record["maintenance"] = _compact_store_result(maintenance)
        elif not decision.ok:
            issue = store.add_issue({"reason": ",".join(decision.blockers), "kind": lane, "payload": dict(record)})
            record["issue"] = _compact_store_result(issue)
        else:
            applied = runtime.gate.approve(int(pp.id), mode="apply")
            record["apply"] = _result_to_dict(applied)
            if getattr(applied, "ok", False):
                lane_counts[lane] = int(lane_counts.get(lane, 0)) + 1
                status = store.load_status()
                counters = dict(status.get("counters") or {})
                counters["auto_applied"] = int(counters.get("auto_applied") or 0) + 1
                status["counters"] = counters
                status["latest_apply"] = record["apply"]
                store.save_status(status)
            else:
                issue = store.add_issue({"reason": getattr(applied, "error", "apply_failed"), "kind": lane, "payload": dict(record)})
                record["issue"] = _compact_store_result(issue)
        store.append_journal("autoplay_proposal", record)
        results.append(record)
    return results


def status_summary(status: dict[str, Any]) -> str:
    readiness = status.get("readiness") or {}
    llm = status.get("llm") or {}
    session = status.get("active_session") or {}
    counters = status.get("counters") or {}
    return " ".join(
        [
            f"status={status.get('status')}",
            f"running={str(bool(status.get('running'))).lower()}",
            f"paused={str(bool(status.get('paused'))).lower()}",
            f"player_guid={session.get('character_guid') or '(none)'}",
            f"readiness={str(bool(readiness.get('ok'))).lower()}",
            f"llm={str(bool(llm.get('ok'))).lower()}",
            f"ticks={counters.get('ticks', 0)}",
            f"issues={len(status.get('issues') or [])}",
            f"maintenance={len(status.get('maintenance_pending') or [])}",
        ]
    )


def _wow_client_running() -> bool:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq wow.exe"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return "wow.exe" in (completed.stdout or "").lower()


def _is_scoped_player_online(session: dict[str, Any] | None) -> bool:
    # DB-backed online checks are intentionally not hidden in this helper. The
    # first safe default is "client process running means not a DBC-safe window";
    # a future BridgeLab-specific implementation can add character.online reads.
    return False if session is None else False


def _schema_from_proposal(proposal: Any) -> str:
    payload = getattr(proposal, "payload", {}) or {}
    if isinstance(payload, dict) and payload.get("schema_version"):
        return str(payload["schema_version"])
    kind = getattr(getattr(proposal, "kind", None), "value", "")
    return {
        "quest": "wm.quest.release.repeatable_bounty.v1",
        "item": "wm.item.release.managed_power.v1",
        "spell": "wm.spell.release.managed_spell.v1",
        "ability": "wm.ability.release.shell_power.v1",
        "scene": "wm.scene.release.native_sequence.v1",
        "action": "control.proposal.v1",
    }.get(str(kind), "unknown")


def _risk_from_proposal(proposal: Any) -> str:
    payload = getattr(proposal, "payload", {}) or {}
    if isinstance(payload, dict):
        risk = payload.get("risk")
        if isinstance(risk, dict) and risk.get("level"):
            return str(risk["level"])
        if isinstance(risk, str):
            return risk
        steps = payload.get("steps")
        if isinstance(steps, list):
            risks = [str(step.get("risk_level") or "low") for step in steps if isinstance(step, dict)]
            if "high" in risks:
                return "high"
            if "medium" in risks:
                return "medium"
    return "low"


def _source_event_at(proposal: Any) -> str | None:
    prov = getattr(proposal, "provenance", {}) or {}
    if isinstance(prov, dict):
        return prov.get("source_event_at") or prov.get("occurred_at")
    return None


def _rollback_available(gate: Any, lane: str) -> bool:
    rollbacks = getattr(gate, "_rollbacks", {})
    if lane in {"quest", "item", "spell"}:
        return lane in rollbacks
    return True


def _dry_run_pending(gate: Any, proposal_id: int) -> Any:
    if hasattr(gate, "dry_run"):
        return gate.dry_run(int(proposal_id))
    return gate.approve(int(proposal_id), mode="dry-run")


def _result_to_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    payload = {}
    for key in ("ok", "detail", "error"):
        if hasattr(result, key):
            payload[key] = getattr(result, key)
    if payload:
        return payload
    try:
        return json.loads(json.dumps(result, default=str))
    except TypeError:
        return {"value": str(result)}


def _compact_store_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key in {"at", "reason", "kind", "detail"}
    }
