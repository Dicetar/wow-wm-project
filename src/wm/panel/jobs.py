from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from wm.panel.catalog import CommandCatalog
from wm.panel.catalog import CommandEntry
from wm.panel.state import PanelState
from wm.panel.state import utc_now_iso


MARKER_SESSION_MAX_AGE_SECONDS = 900

JOB_STATES = {
    "DRAFT",
    "VALIDATED",
    "DRY_RUN_PASSED",
    "AWAITING_CONFIRM",
    "APPLIED",
    "REJECTED",
    "INVALID",
    "BROKEN",
}


@dataclass(slots=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "argv": self.argv,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


class JobRunner:
    def __init__(
        self,
        *,
        state: PanelState,
        catalog: CommandCatalog | None = None,
        cwd: str | Path | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self.state = state
        self.catalog = catalog or CommandCatalog()
        self.cwd = Path(cwd) if cwd is not None else Path.cwd()
        self.timeout_seconds = int(timeout_seconds)

    def run_dry_run(self, *, command_id: str, params: dict[str, Any] | None = None, payload: Any = None) -> dict[str, Any]:
        try:
            entry = self.catalog.get(command_id)
        except KeyError as exc:
            job = self._new_job(command_id=command_id, params=params or {}, payload=payload)
            job["state"] = "INVALID"
            job["issues"].append({"path": "command_id", "message": str(exc), "severity": "error"})
            self.state.save_job(job)
            return job
        resolved_params = dict(params or {})
        if entry.marker_target_required:
            try:
                resolved_params = self._resolve_marker_target(resolved_params)
            except ValueError as exc:
                job = self._new_job(command_id=command_id, params=resolved_params, payload=payload)
                job["state"] = "INVALID"
                job["issues"].append({"path": "params.player_guid", "message": str(exc), "severity": "error"})
                self.state.save_job(job)
                return job
        job = self._new_job(command_id=command_id, params=resolved_params, payload=payload)
        try:
            argv = entry.argv_for(mode="dry-run", params=job["params"], paths=self._job_paths(job))
        except Exception as exc:
            job["state"] = "INVALID"
            job["issues"].append({"path": "params", "message": str(exc), "severity": "error"})
            self.state.save_job(job)
            return job
        job["state"] = "VALIDATED"
        result = self._run(argv)
        job["dry_run"] = result.to_dict()
        job["state"] = "AWAITING_CONFIRM" if result.returncode == 0 and entry.mutating else ("DRY_RUN_PASSED" if result.returncode == 0 else "BROKEN")
        job["updated_at"] = utc_now_iso()
        self.state.save_job(job)
        return job

    def _resolve_marker_target(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self.state.load_session() or {}
        guid = _validate_marker_session(session)
        explicit = params.get("player_guid")
        if explicit not in (None, "") and int(explicit) != int(guid):
            raise ValueError("explicit player_guid conflicts with the active marker-selected WM Session")
        return {**params, "player_guid": int(guid)}

    def run_apply(self, *, job_id: str, confirmation: str | None = None) -> dict[str, Any]:
        job = self.state.load_job(job_id)
        if job is None:
            return self._error_job(job_id=job_id, message="Job not found.")
        try:
            entry = self.catalog.get(str(job["command_id"]))
        except KeyError as exc:
            job["issues"].append({"path": "command_id", "message": str(exc), "severity": "error"})
            job["state"] = "INVALID"
            self.state.save_job(job)
            return job
        if not entry.mutating:
            job["issues"].append({"path": "command_id", "message": "Read-only commands cannot be applied.", "severity": "error"})
            job["state"] = "INVALID"
            self.state.save_job(job)
            return job
        if entry.dry_run_required and job.get("state") not in {"AWAITING_CONFIRM", "DRY_RUN_PASSED"}:
            job["issues"].append({"path": "state", "message": "Apply requires a passing dry-run first.", "severity": "error"})
            job["state"] = "INVALID"
            self.state.save_job(job)
            return job
        if entry.confirmation == "type_job_id" and confirmation != job_id:
            attempts = list(job.get("apply_attempts") or [])
            attempts.append(
                {
                    "created_at": utc_now_iso(),
                    "ok": False,
                    "path": "confirmation",
                    "message": "Confirmation must match the job id.",
                    "severity": "error",
                }
            )
            job["apply_attempts"] = attempts
            job["updated_at"] = utc_now_iso()
            self.state.save_job(job)
            return job
        if entry.marker_target_required:
            try:
                job["params"] = self._resolve_marker_target(dict(job.get("params") or {}))
            except ValueError as exc:
                job["issues"].append({"path": "params.player_guid", "message": str(exc), "severity": "error"})
                job["state"] = "INVALID"
                job["updated_at"] = utc_now_iso()
                self.state.save_job(job)
                return job
        try:
            argv = entry.argv_for(mode="apply", params=dict(job.get("params") or {}), paths=self._job_paths(job))
        except Exception as exc:
            job["issues"].append({"path": "params", "message": str(exc), "severity": "error"})
            job["state"] = "INVALID"
            self.state.save_job(job)
            return job
        result = self._run(argv)
        job["apply"] = result.to_dict()
        job["state"] = "APPLIED" if result.returncode == 0 else "BROKEN"
        job["updated_at"] = utc_now_iso()
        self.state.save_job(job)
        return job

    def _new_job(self, *, command_id: str, params: dict[str, Any], payload: Any) -> dict[str, Any]:
        job_id = self.state.new_id("job")
        job_dir = self.state.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        if payload is not None:
            (job_dir / "input.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
            if isinstance(payload, dict) and payload.get("schema_version") == "control.proposal.v1":
                (job_dir / "proposal.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "job_id": job_id,
            "command_id": command_id,
            "params": dict(params),
            "state": "DRAFT",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "issues": [],
            "paths": {key: str(value) for key, value in self._paths_for_dir(job_dir).items()},
        }

    def _job_paths(self, job: dict[str, Any]) -> dict[str, Path]:
        paths = job.get("paths")
        if isinstance(paths, dict) and paths:
            return {key: Path(value) for key, value in paths.items()}
        return self._paths_for_dir(self.state.job_dir(str(job["job_id"])))

    @staticmethod
    def _paths_for_dir(job_dir: Path) -> dict[str, Path]:
        return {
            "job_dir": job_dir,
            "input_json": job_dir / "input.json",
            "proposal_json": job_dir / "proposal.json",
            "context_pack_json": job_dir / "context-pack.json",
            "candidate_dir": job_dir / "candidates",
            "packet_dir": job_dir / "packet",
            "result_json": job_dir / "result.json",
        }

    def _run(self, argv: list[str]) -> CommandResult:
        try:
            completed = subprocess.run(
                argv,
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                argv=argv,
                returncode=124,
                stdout=str(exc.stdout or ""),
                stderr=f"Command timed out after {self.timeout_seconds} seconds.",
            )
        except OSError as exc:
            return CommandResult(argv=argv, returncode=127, stdout="", stderr=str(exc))
        return CommandResult(
            argv=argv,
            returncode=int(completed.returncode),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    @staticmethod
    def _error_job(*, job_id: str, message: str) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "state": "BROKEN",
            "issues": [{"path": "job_id", "message": message, "severity": "error"}],
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }


def _validate_marker_session(session: dict[str, Any]) -> int:
    if session.get("source") != "marker" or int(session.get("marker_spell_id") or 0) != 946602:
        raise ValueError("a canonical marker-selected WM Session is required")
    guid = session.get("character_guid")
    if guid in (None, ""):
        raise ValueError("the active marker-selected WM Session has no character GUID")
    if session.get("bridge_event_id") in (None, ""):
        raise ValueError("the active marker-selected WM Session has no bridge event id")
    marker = session.get("marker") if isinstance(session.get("marker"), dict) else {}
    if marker.get("character_online") is not True:
        raise ValueError("the active marker-selected WM Session target is not confirmed online")
    selected_at = _parse_utc(session.get("selected_at"))
    if selected_at is None:
        raise ValueError("the active marker-selected WM Session has no valid selection time")
    age = (datetime.now(timezone.utc) - selected_at).total_seconds()
    if age > MARKER_SESSION_MAX_AGE_SECONDS:
        raise ValueError("the active marker-selected WM Session is stale")
    return int(guid)


def _parse_utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
