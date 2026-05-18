from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlparse

from wm.llm.lmstudio import LmStudioClient
from wm.llm.lmstudio import LmStudioSettings
from wm.panel.catalog import CommandCatalog
from wm.panel.jobs import JobRunner
from wm.panel.schemas import SchemaCatalog
from wm.panel.state import PanelState
from wm.panel.state import utc_now_iso


class PanelApp:
    def __init__(
        self,
        *,
        state: PanelState | None = None,
        schema_catalog: SchemaCatalog | None = None,
        command_catalog: CommandCatalog | None = None,
        cwd: str | Path | None = None,
    ) -> None:
        self.state = state or PanelState()
        self.state.ensure()
        self.cwd = Path(cwd) if cwd is not None else Path.cwd()
        self.cwd = self.cwd.resolve()
        self.schema_catalog = schema_catalog or SchemaCatalog.load()
        self.command_catalog = command_catalog or CommandCatalog()
        self.job_runner = JobRunner(state=self.state, catalog=self.command_catalog, cwd=self.cwd)
        self._api_key: str | None = None

    def get(self, raw_path: str) -> tuple[int, Any]:
        path = urlparse(raw_path).path
        if path == "/api/status":
            return 200, self._status()
        if path == "/api/catalog":
            return 200, {"commands": self.command_catalog.list_api()}
        if path == "/api/schemas":
            return 200, {"schemas": self.schema_catalog.list_api()}
        if path.startswith("/api/schemas/"):
            schema_version = unquote(path.removeprefix("/api/schemas/"))
            try:
                return 200, self.schema_catalog.get(schema_version).to_dict()
            except KeyError as exc:
                return 404, {"ok": False, "error": str(exc)}
        if path.startswith("/api/jobs/"):
            job_id = unquote(path.removeprefix("/api/jobs/"))
            job = self.state.load_job(job_id)
            return (200, job) if job is not None else (404, {"ok": False, "error": "Job not found."})
        if path == "/api/drafts":
            return 200, {"drafts": self.state.list_drafts()}
        if path.startswith("/api/drafts/"):
            draft_id = unquote(path.removeprefix("/api/drafts/"))
            draft = self.state.load_draft(draft_id)
            return (200, draft) if draft is not None else (404, {"ok": False, "error": "Draft not found."})
        if path == "/api/llm/settings":
            settings = self.state.load_settings()
            return 200, {**settings, "api_key_set": bool(self._api_key)}
        if path == "/api/llm/models":
            settings = LmStudioSettings.from_dict({**self.state.load_settings(), "api_key": self._api_key})
            try:
                return 200, {"ok": True, "models": LmStudioClient(settings).list_models()}
            except Exception as exc:
                return 200, {"ok": False, "models": [], "error": str(exc)}
        if path == "/api/living":
            try:
                from wm.living.catalog import build_wild_feature_catalog
                return 200, build_wild_feature_catalog()
            except Exception as exc:
                return 200, {"ok": False, "error": str(exc)}
        return 404, {"ok": False, "error": "Not found."}

    def post(self, raw_path: str, body: dict[str, Any]) -> tuple[int, Any]:
        path = urlparse(raw_path).path
        if path == "/api/schema/validate":
            schema_version = str(body.get("schema_version") or (body.get("payload") or {}).get("schema_version") or "")
            return 200, self.schema_catalog.validate(schema_version, body.get("payload"))
        if path == "/api/jobs/dry-run":
            return 200, self.job_runner.run_dry_run(
                command_id=str(body.get("command_id") or ""),
                params=dict(body.get("params") or {}),
                payload=body.get("payload"),
            )
        if path == "/api/jobs/apply":
            return 200, self.job_runner.run_apply(
                job_id=str(body.get("job_id") or ""),
                confirmation=(str(body.get("confirmation")) if body.get("confirmation") is not None else None),
            )
        if path == "/api/llm/settings":
            if body.get("api_key") not in (None, ""):
                self._api_key = str(body["api_key"])
            settings = self.state.save_settings(dict(body))
            return 200, {**settings, "api_key_set": bool(self._api_key)}
        if path == "/api/llm/generate":
            return 200, self._generate_llm_draft(body)
        if path.startswith("/api/drafts/") and path.endswith("/reject"):
            draft_id = unquote(path.removeprefix("/api/drafts/").removesuffix("/reject"))
            return self._update_draft_state(draft_id=draft_id, state="REJECTED")
        if path.startswith("/api/drafts/") and path.endswith("/adopt"):
            draft_id = unquote(path.removeprefix("/api/drafts/").removesuffix("/adopt"))
            return self._adopt_draft(draft_id=draft_id, body=body)
        return 404, {"ok": False, "error": "Not found."}

    def _generate_llm_draft(self, body: dict[str, Any]) -> dict[str, Any]:
        schema_version = str(body.get("schema_version") or "")
        instruction = str(body.get("instruction") or "").strip()
        settings = self._llm_settings(body.get("settings") if isinstance(body.get("settings"), dict) else {})
        draft_id = self.state.new_id("draft")
        base_draft = {
            "draft_id": draft_id,
            "origin": "llm",
            "schema_version": schema_version,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "settings": settings.to_safe_dict(),
            "instruction": instruction,
            "context_pack_path": body.get("context_pack_path"),
            "candidate_pack_path": body.get("candidate_pack_path"),
        }
        try:
            entry = self.schema_catalog.get(schema_version)
            context_pack = _load_json_or_value(body, "context_pack", "context_pack_path", workspace_root=self.cwd)
            candidate_pack = _load_json_or_value(body, "candidate_pack", "candidate_pack_path", workspace_root=self.cwd)
            result = LmStudioClient(settings).generate_json(
                schema_version=schema_version,
                schema=entry.schema,
                instruction=instruction,
                context_pack=context_pack,
                candidate_pack=candidate_pack,
            )
            validation = self.schema_catalog.validate(schema_version, result["parsed"])
            draft = {
                **base_draft,
                "state": "VALIDATED" if validation["ok"] else "INVALID",
                "raw_response": result["raw"],
                "content": result["content"],
                "parsed_json": result["parsed"],
                "validation": validation,
            }
        except Exception as exc:
            draft = {
                **base_draft,
                "state": "BROKEN",
                "error": str(exc),
                "parsed_json": None,
                "validation": {
                    "ok": False,
                    "issues": [{"path": "llm", "message": str(exc), "severity": "error"}],
                },
            }
        self.state.save_draft(draft)
        return draft

    def _llm_settings(self, overrides: dict[str, Any]) -> LmStudioSettings:
        settings = self.state.load_settings()
        settings.update({key: value for key, value in overrides.items() if value not in (None, "")})
        if overrides.get("api_key") not in (None, ""):
            self._api_key = str(overrides["api_key"])
        settings["api_key"] = self._api_key
        return LmStudioSettings.from_dict(settings)

    def _update_draft_state(self, *, draft_id: str, state: str) -> tuple[int, Any]:
        draft = self.state.load_draft(draft_id)
        if draft is None:
            return 404, {"ok": False, "error": "Draft not found."}
        draft["state"] = state
        draft["updated_at"] = utc_now_iso()
        self.state.save_draft(draft)
        return 200, draft

    def _adopt_draft(self, *, draft_id: str, body: dict[str, Any]) -> tuple[int, Any]:
        source = self.state.load_draft(draft_id)
        if source is None:
            return 404, {"ok": False, "error": "Draft not found."}
        parsed = source.get("parsed_json")
        if not isinstance(parsed, dict):
            return 400, {"ok": False, "error": "Draft has no parsed JSON to adopt."}
        adopted_payload = json.loads(json.dumps(parsed))
        if adopted_payload.get("schema_version") == "control.proposal.v1":
            metadata = adopted_payload.setdefault("metadata", {})
            if isinstance(metadata, dict):
                metadata["original_llm_draft_id"] = draft_id
                metadata["original_llm_settings"] = source.get("settings")
            author = adopted_payload.setdefault("author", {})
            if isinstance(author, dict) and author.get("kind") == "llm":
                author["kind"] = "manual"
                author["name"] = str(body.get("operator_name") or "operator-reviewed")
        adopted = {
            "draft_id": self.state.new_id("draft"),
            "origin": "human_reviewed",
            "parent_draft_id": draft_id,
            "schema_version": source.get("schema_version"),
            "state": "DRAFT",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "parsed_json": adopted_payload,
            "validation": self.schema_catalog.validate(str(source.get("schema_version") or ""), adopted_payload),
            "original_llm_metadata": {
                "draft_id": draft_id,
                "settings": source.get("settings"),
                "instruction": source.get("instruction"),
            },
        }
        self.state.save_draft(adopted)
        return 200, adopted

    def _status(self) -> dict[str, Any]:
        return {
            "status": "PARTIAL",
            "panel": "WM Local Control Panel",
            "state_root": str(self.state.root),
            "schema_count": len(self.schema_catalog.entries),
            "command_count": len(self.command_catalog.entries),
            "latest_job": (self.state.list_jobs(limit=1) or [None])[0],
            "latest_draft": (self.state.list_drafts(limit=1) or [None])[0],
            "git": _git_status(),
            "llm": {**self.state.load_settings(), "api_key_set": bool(self._api_key)},
        }


def serve(*, host: str = "127.0.0.1", port: int = 8765, state_root: Path | None = None) -> None:
    app = PanelApp(state=PanelState(state_root) if state_root is not None else None)
    handler = _handler_for(app)
    server = ThreadingHTTPServer((host, int(port)), handler)
    print(f"WM panel listening on http://{host}:{int(port)}")
    server.serve_forever()


def _handler_for(app: PanelApp) -> type[BaseHTTPRequestHandler]:
    static_root = Path(__file__).parent / "static"

    class PanelRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/" or self.path.startswith("/static/"):
                self._send_static(static_root)
                return
            status, payload = app.get(self.path)
            self._send_json(status, payload)

        def do_POST(self) -> None:  # noqa: N802
            try:
                body = self._read_json_body()
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            status, payload = app.post(self.path, body)
            self._send_json(status, payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > 10 * 1024 * 1024:
                raise ValueError("Request body is too large.")
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            parsed = json.loads(raw or "{}")
            if not isinstance(parsed, dict):
                raise ValueError("Request body must be a JSON object.")
            return parsed

        def _send_json(self, status: int, payload: Any) -> None:
            raw = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_static(self, root: Path) -> None:
            requested = "index.html" if self.path == "/" else unquote(self.path.removeprefix("/static/"))
            path = (root / requested).resolve()
            if root.resolve() not in path.parents and path != root.resolve():
                self._send_json(403, {"ok": False, "error": "Forbidden."})
                return
            if not path.exists() or not path.is_file():
                self._send_json(404, {"ok": False, "error": "Not found."})
                return
            content_type = _content_type(path)
            raw = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    return PanelRequestHandler


def _load_json_or_value(body: dict[str, Any], value_key: str, path_key: str, *, workspace_root: Path) -> Any | None:
    if value_key in body:
        return body[value_key]
    path_value = body.get(path_key)
    if path_value in (None, ""):
        return None
    path = _resolve_workspace_json_path(str(path_value), workspace_root=workspace_root)
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_workspace_json_path(path_value: str, *, workspace_root: Path) -> Path:
    root = workspace_root.resolve()
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path must stay inside WM workspace: {path_value}") from exc
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"JSON path not found: {path_value}")
    return resolved


def _git_status() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=3,
            shell=False,
        )
    except Exception as exc:
        return {"ok": False, "dirty": None, "error": str(exc)}
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return {"ok": completed.returncode == 0, "dirty": bool(lines), "lines": lines[:50]}


def _content_type(path: Path) -> str:
    if path.suffix == ".html":
        return "text/html; charset=utf-8"
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    if path.suffix == ".js":
        return "text/javascript; charset=utf-8"
    return "application/octet-stream"
