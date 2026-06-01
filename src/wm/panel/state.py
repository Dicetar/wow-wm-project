from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any


DEFAULT_PANEL_SETTINGS: dict[str, Any] = {
    "base_url": "http://localhost:1234/v1",
    "model": None,
    "temperature": 0.2,
    "top_p": None,
    "max_tokens": 2048,
    "timeout_seconds": 60,
    "schema_mode": "json_schema",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class PanelState:
    root: Path = Path(".wm-bootstrap/state/control-panel")

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("jobs", "drafts", "schemas", "artifacts"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    @property
    def settings_path(self) -> Path:
        return self.root / "settings.json"

    @property
    def session_path(self) -> Path:
        return self.root / "session.json"

    def load_settings(self) -> dict[str, Any]:
        self.ensure()
        settings = dict(DEFAULT_PANEL_SETTINGS)
        if self.settings_path.exists():
            raw = self.read_json(self.settings_path)
            if isinstance(raw, dict):
                settings.update({key: value for key, value in raw.items() if key != "api_key"})
        return settings

    def save_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        self.ensure()
        sanitized = dict(DEFAULT_PANEL_SETTINGS)
        sanitized.update({key: value for key, value in settings.items() if key in DEFAULT_PANEL_SETTINGS})
        sanitized.pop("api_key", None)
        self.write_json(self.settings_path, sanitized)
        return sanitized

    def load_session(self) -> dict[str, Any] | None:
        self.ensure()
        if not self.session_path.exists():
            return None
        raw = self.read_json(self.session_path)
        return raw if isinstance(raw, dict) else None

    def save_session(self, session: dict[str, Any]) -> dict[str, Any]:
        self.ensure()
        self.write_json(self.session_path, session)
        return session

    def new_id(self, prefix: str) -> str:
        return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    def job_dir(self, job_id: str) -> Path:
        return self.root / "jobs" / job_id

    def draft_path(self, draft_id: str) -> Path:
        return self.root / "drafts" / f"{draft_id}.json"

    def save_job(self, job: dict[str, Any]) -> None:
        self.ensure()
        job_id = str(job["job_id"])
        directory = self.job_dir(job_id)
        directory.mkdir(parents=True, exist_ok=True)
        self.write_json(directory / "job.json", job)

    def load_job(self, job_id: str) -> dict[str, Any] | None:
        path = self.job_dir(job_id) / "job.json"
        if not path.exists():
            return None
        raw = self.read_json(path)
        return raw if isinstance(raw, dict) else None

    def list_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        self.ensure()
        jobs: list[dict[str, Any]] = []
        for path in sorted((self.root / "jobs").glob("*/job.json"), reverse=True):
            raw = self.read_json(path)
            if isinstance(raw, dict):
                jobs.append(raw)
            if len(jobs) >= limit:
                break
        return jobs

    def save_draft(self, draft: dict[str, Any]) -> None:
        self.ensure()
        self.write_json(self.draft_path(str(draft["draft_id"])), draft)

    def load_draft(self, draft_id: str) -> dict[str, Any] | None:
        path = self.draft_path(draft_id)
        if not path.exists():
            return None
        raw = self.read_json(path)
        return raw if isinstance(raw, dict) else None

    def list_drafts(self, *, limit: int = 50) -> list[dict[str, Any]]:
        self.ensure()
        drafts: list[dict[str, Any]] = []
        for path in sorted((self.root / "drafts").glob("*.json"), reverse=True):
            raw = self.read_json(path)
            if isinstance(raw, dict):
                drafts.append(raw)
            if len(drafts) >= limit:
                break
        return drafts

    @staticmethod
    def read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
