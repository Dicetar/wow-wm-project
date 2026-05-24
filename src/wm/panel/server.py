from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from typing import Any, Callable
from urllib.parse import unquote
from urllib.parse import parse_qs
from urllib.parse import urlparse

from wm.llm.lmstudio import LmStudioClient
from wm.llm.lmstudio import LmStudioSettings
from wm.panel.catalog import CommandCatalog
from wm.panel.jobs import JobRunner
from wm.panel.schemas import SchemaCatalog
from wm.panel.state import PanelState
from wm.panel.state import utc_now_iso
from wm.sources.native_bridge.player_marker import DEFAULT_MARKER_SPELL_ID

# slice runtime types — imported lazily inside method bodies to keep
# panel tests light when the slice deps aren't needed.

SliceFactory = Any            # Callable[..., SliceRuntime]
SliceDiscoverer = Any         # Callable[[], int | None]
SlicePumpFactory = Any        # Callable[[SliceRuntime], BridgeEventPump]
MarkerDiscoverer = Any        # Callable[..., list[dict[str, Any]]]


class PanelApp:
    def __init__(
        self,
        *,
        state: PanelState | None = None,
        schema_catalog: SchemaCatalog | None = None,
        command_catalog: CommandCatalog | None = None,
        cwd: str | Path | None = None,
        slice_factory: SliceFactory | None = None,
        slice_discoverer: SliceDiscoverer | None = None,
        slice_pump_factory: SlicePumpFactory | None = None,
        marker_discoverer: MarkerDiscoverer | None = None,
        character_reader: Callable[[int], Any] | None = None,
    ) -> None:
        self.state = state or PanelState()
        self.state.ensure()
        self.cwd = Path(cwd) if cwd is not None else Path.cwd()
        self.cwd = self.cwd.resolve()
        self.schema_catalog = schema_catalog or SchemaCatalog.load()
        self.command_catalog = command_catalog or CommandCatalog()
        self.job_runner = JobRunner(state=self.state, catalog=self.command_catalog, cwd=self.cwd)
        self._api_key: str | None = None
        self._slice: Any | None = None
        self._slice_pump: Any | None = None
        self._slice_factory = slice_factory
        self._slice_discoverer = slice_discoverer
        self._slice_pump_factory = slice_pump_factory
        self._marker_discoverer = marker_discoverer
        self._character_reader = character_reader

    def get(self, raw_path: str) -> tuple[int, Any]:
        parsed_url = urlparse(raw_path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
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
        if path == "/api/health":
            return 200, {"ok": True, "status": "healthy", "panel": "WM Local Control Panel"}
        if path == "/api/feature_status":
            return 200, self._feature_status()
        if path == "/api/living_readiness":
            return 200, self._living_readiness()
        if path == "/api/proposals":
            return 200, {"proposals": self.state.list_drafts(limit=100)}
        if path == "/api/wm/readiness":
            return 200, self._wm_readiness()
        if path == "/api/wm/markers":
            return 200, self._wm_markers(
                since_seconds=_query_int(query, "since_seconds", 300),
                limit=_query_int(query, "limit", 20),
                marker_spell_id=_query_int(query, "marker_spell_id", DEFAULT_MARKER_SPELL_ID),
            )
        if path == "/api/wm/session/overview":
            return self._wm_session_overview()
        if path == "/api/wm/session/status":
            return self._slice_status()
        if path == "/api/wm/inbox":
            return self._slice_inbox(
                kind=_query_str(query, "kind"),
                character_guid=_query_int(query, "character_guid", 0),
            )
        if path == "/api/wm/session/pending":
            return self._slice_pending()
        if path == "/api/wm/session/issues":
            return self._slice_issues()
        if path == "/api/wm/session/log":
            return self._slice_log()
        if path == "/api/slice/status":
            return self._slice_status()
        if path == "/api/slice/pending":
            return self._slice_pending()
        if path == "/api/slice/issues":
            return self._slice_issues()
        if path == "/api/slice/log":
            return self._slice_log()
        return 404, {"ok": False, "error": "Not found."}

    def _require_slice(self) -> tuple[int, Any] | None:
        if self._slice is None:
            return 404, {"ok": False, "error": "WM session not bootstrapped"}
        return None

    def _slice_status(self) -> tuple[int, Any]:
        if (err := self._require_slice()) is not None:
            return err
        rt = self._slice
        session = self.state.load_session()
        return 200, {
            "ok": True,
            "character_guid": rt.runner.module.character_guid,
            "session": session,
            "current_beat": rt.runner.current_beat_id,
            "pending_count": len(rt.gate.pending()),
            "issues_count": len(rt.issues.list_open()),
            "applied_log_size": len(rt.applied_log),
        }

    def _slice_pending(self) -> tuple[int, Any]:
        if (err := self._require_slice()) is not None:
            return err
        rt = self._slice
        items = []
        for pp in rt.gate.pending():
            p = pp.proposal
            items.append({
                "id": pp.id,
                "kind": p.kind.value,
                "character_guid": p.character_guid,
                "narrative_summary": p.narrative_summary,
                "payload": p.payload,
                "provenance": p.provenance,
            })
        return 200, {"pending": items}

    def _slice_inbox(self, *, kind: str | None = None, character_guid: int = 0) -> tuple[int, Any]:
        if (err := self._require_slice()) is not None:
            return err
        rt = self._slice
        items = []
        for pp in rt.gate.pending():
            p = pp.proposal
            if kind is not None and p.kind.value != kind:
                continue
            if character_guid and int(p.character_guid) != int(character_guid):
                continue
            items.append({
                "id": pp.id,
                "kind": p.kind.value,
                "character_guid": p.character_guid,
                "narrative_summary": p.narrative_summary,
                "payload": p.payload,
                "provenance": p.provenance,
            })
        return 200, {"pending": items}

    def _slice_issues(self) -> tuple[int, Any]:
        if (err := self._require_slice()) is not None:
            return err
        rt = self._slice
        items = []
        for it in rt.issues.list_open():
            items.append({
                "id": it.id,
                "kind": it.kind,
                "character_guid": it.character_guid,
                "reason": it.reason,
                "payload": it.payload,
                "provenance": it.provenance,
            })
        return 200, {"issues": items}

    def _slice_log(self, *, limit: int = 50) -> tuple[int, Any]:
        if (err := self._require_slice()) is not None:
            return err
        rt = self._slice
        log = list(rt.applied_log)[-limit:]
        return 200, {"log": log}

    def _wm_readiness(self) -> dict[str, Any]:
        status = self._status()
        payload: dict[str, Any] = {
            "ok": True,
            "panel_status": status["status"],
            "active_session": self.state.load_session(),
            "git": status["git"],
            "marker_spell_id": DEFAULT_MARKER_SPELL_ID,
        }
        try:
            from wm.config import Settings
            from wm.doctor import run_doctor

            checks = run_doctor(Settings.from_env())
            payload["doctor"] = {
                "ok": not any(check.status == "FAIL" for check in checks),
                "checks": [check.to_dict() for check in checks],
            }
        except Exception as exc:
            payload["doctor"] = {"ok": False, "error": str(exc), "checks": []}
        return payload

    def _wm_session_overview(self) -> tuple[int, Any]:
        session = self.state.load_session()
        guid = (session or {}).get("character_guid")
        if guid in (None, ""):
            return 400, {"ok": False, "error": "no active session; bootstrap a character first"}
        guid = int(guid)
        reader = self._character_reader or _default_character_reader
        try:
            bundle = reader(guid)
        except Exception as exc:
            # Live-DB read failed: 200 with ok=False matches the panel idiom
            # (cf. /api/llm/models) — request understood, live read degraded.
            return 200, {"ok": False, "overview": None, "error": f"character read failed: {exc}"}
        from wm.character.overview import build_character_overview
        readiness = self._wm_readiness().get("doctor")
        proposal_counts = None
        if self._slice is not None:
            try:
                proposal_counts = {
                    "pending": len(self._slice.gate.pending()),
                    "issues": len(self._slice.issues.list_open()),
                }
            except Exception:
                proposal_counts = None  # best-effort enrichment; omit on any error
        overview = build_character_overview(
            player_guid=guid, bundle=bundle,
            readiness=readiness, proposal_counts=proposal_counts,
        )
        return 200, {"ok": True, "overview": overview}

    def _wm_markers(self, *, since_seconds: int = 300, limit: int = 20, marker_spell_id: int = DEFAULT_MARKER_SPELL_ID) -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []
        if self._marker_discoverer is not None:
            candidates = list(self._marker_discoverer(
                since_seconds=int(since_seconds),
                limit=int(limit),
                marker_spell_id=int(marker_spell_id),
            ))
        return {
            "ok": True,
            "marker_spell_id": int(marker_spell_id),
            "since_seconds": int(since_seconds),
            "count": len(candidates),
            "candidates": candidates,
        }

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
        if path == "/api/llm/adopt":
            return 200, self._log_llm_adoption(body)
        if path == "/api/wm/session/bootstrap":
            return self._slice_bootstrap(body)
        if path == "/api/wm/session/approve":
            return self._slice_approve(body)
        if path == "/api/wm/session/reject":
            return self._slice_reject(body)
        if path == "/api/wm/rollback":
            return self._slice_rollback(body)
        if path == "/api/wm/session/poll":
            return self._slice_poll(body)
        if path == "/api/slice/bootstrap":
            return self._slice_bootstrap(body)
        if path == "/api/slice/approve":
            return self._slice_approve(body)
        if path == "/api/slice/reject":
            return self._slice_reject(body)
        if path == "/api/slice/poll":
            return self._slice_poll(body)
        return 404, {"ok": False, "error": "Not found."}

    def _slice_approve(self, body: dict[str, Any]) -> tuple[int, Any]:
        if (err := self._require_slice()) is not None:
            return err
        pid_raw = body.get("id")
        if pid_raw in (None, ""):
            return 400, {"ok": False, "error": "id is required"}
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            return 400, {"ok": False, "error": "id must be an integer"}
        try:
            result = self._slice.gate.approve(pid)
        except Exception as exc:
            return 500, {"ok": False, "error": f"approve failed: {exc}"}
        return 200, {
            "ok": bool(getattr(result, "ok", False)),
            "id": pid,
            "detail": getattr(result, "detail", None),
            "error": getattr(result, "error", None),
        }

    def _slice_rollback(self, body: dict[str, Any]) -> tuple[int, Any]:
        if (err := self._require_slice()) is not None:
            return err
        artifact_type = str(body.get("artifact_type") or "").strip()
        if not artifact_type:
            return 400, {"ok": False, "error": "artifact_type is required"}
        entry_raw = body.get("artifact_entry")
        if entry_raw in (None, ""):
            return 400, {"ok": False, "error": "artifact_entry is required"}
        try:
            artifact_entry = int(entry_raw)
        except (TypeError, ValueError):
            return 400, {"ok": False, "error": "artifact_entry must be an integer"}
        mode = str(body.get("mode") or "apply")
        try:
            result = self._slice.gate.rollback(
                artifact_type=artifact_type, artifact_entry=artifact_entry, mode=mode)
        except Exception as exc:
            return 500, {"ok": False, "error": f"rollback failed: {exc}"}
        return 200, {
            "ok": bool(getattr(result, "ok", False)),
            "artifact_type": artifact_type,
            "artifact_entry": artifact_entry,
            "detail": getattr(result, "detail", None),
            "error": getattr(result, "error", None),
        }

    def _slice_reject(self, body: dict[str, Any]) -> tuple[int, Any]:
        if (err := self._require_slice()) is not None:
            return err
        pid_raw = body.get("id")
        if pid_raw in (None, ""):
            return 400, {"ok": False, "error": "id is required"}
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            return 400, {"ok": False, "error": "id must be an integer"}
        reason = str(body.get("reason") or "operator-rejected")
        try:
            self._slice.gate.reject(pid, reason=reason)
        except Exception as exc:
            return 500, {"ok": False, "error": f"reject failed: {exc}"}
        return 200, {"ok": True, "id": pid, "reason": reason}

    def _slice_poll(self, _body: dict[str, Any]) -> tuple[int, Any]:
        if (err := self._require_slice()) is not None:
            return err
        if self._slice_pump is None:
            return 409, {"ok": False, "error": "no pump wired; bootstrap with a pump_factory"}
        try:
            n = self._slice_pump.poll_once()
        except Exception as exc:
            return 500, {"ok": False, "error": f"pump failed: {exc}"}
        return 200, {"ok": True, "events_seen": int(n),
                     "last_seen_event_id": getattr(self._slice_pump, "last_seen_event_id", None)}

    def _slice_bootstrap(self, body: dict[str, Any]) -> tuple[int, Any]:
        guid_raw = body.get("character_guid")
        session: dict[str, Any]
        if guid_raw in (None, ""):
            try:
                session = self._discover_session_from_marker(body)
            except Exception as exc:
                return 500, {"ok": False, "error": f"discoverer failed: {exc}"}
            if not session:
                return 400, {
                    "ok": False,
                    "error": "no character_guid supplied and none discoverable from marker/spine",
                }
            guid = int(session["character_guid"])
        else:
            try:
                guid = int(guid_raw)
            except (TypeError, ValueError):
                return 400, {"ok": False, "error": "character_guid must be an integer"}
            session = {
                "character_guid": guid,
                "character_name": body.get("character_name"),
                "source": "explicit_guid",
                "marker_spell_id": _body_int(body, "marker_spell_id", DEFAULT_MARKER_SPELL_ID),
                "bridge_event_id": None,
                "selected_at": utc_now_iso(),
            }
        factory = self._slice_factory or _default_slice_factory
        try:
            self._slice = factory(character_guid=guid)
        except Exception as exc:
            return 500, {"ok": False, "error": f"slice factory failed: {exc}"}
        # pump is optional — bootstrap an in-process pump if a factory is configured
        if self._slice_pump_factory is not None:
            try:
                self._slice_pump = self._slice_pump_factory(self._slice)
            except Exception as exc:
                return 500, {"ok": False, "error": f"pump factory failed: {exc}"}
        self.state.save_session(session)
        return 200, {"ok": True, "character_guid": guid, "session": session}

    def _discover_session_from_marker(self, body: dict[str, Any]) -> dict[str, Any]:
        marker_spell_id = _body_int(body, "marker_spell_id", DEFAULT_MARKER_SPELL_ID)
        since_seconds = _body_int(body, "since_seconds", 300)
        if self._marker_discoverer is not None:
            candidates = list(self._marker_discoverer(
                since_seconds=since_seconds,
                limit=10,
                marker_spell_id=marker_spell_id,
            ))
            if candidates:
                return _session_from_marker_candidate(candidates[0], marker_spell_id=marker_spell_id)

        discoverer = self._slice_discoverer or _default_slice_discoverer
        guid = discoverer()
        if guid is None:
            return {}
        return {
            "character_guid": int(guid),
            "character_name": None,
            "source": "marker",
            "marker_spell_id": marker_spell_id,
            "bridge_event_id": None,
            "selected_at": utc_now_iso(),
        }

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

    def _feature_status(self) -> dict[str, Any]:
        try:
            from wm.living.catalog import build_wild_feature_catalog, validate_wild_catalog
            cat = build_wild_feature_catalog()
            issues = validate_wild_catalog()
            return {
                "ok": not issues,
                "live_ready_count": cat["live_ready_count"],
                "total_count": cat["count"],
                "issues": issues,
                "entries": [
                    {"key": e["key"], "live_ready": e["live_ready"], "batch": e["batch"]}
                    for e in cat["entries"]
                ],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _living_readiness(self) -> dict[str, Any]:
        try:
            from wm.living.catalog import dry_run_all
            result = dry_run_all()
            return {
                "ok": result["ok"],
                "dry_run_results": result["results"],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _log_llm_adoption(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            from wm.llm.provenance import ProvenanceLogger
            logger = ProvenanceLogger(db_client=None)
            proposal_id = logger.log(
                schema_version=str(body.get("schema_version") or ""),
                instruction=str(body.get("instruction") or ""),
                raw_response=str(body.get("raw_response") or ""),
                parsed_json=body.get("parsed_json"),
                model_id=body.get("model_id"),
                operator=body.get("operator"),
            )
            return {"ok": True, "proposal_id": proposal_id, "note": "no-db: provenance not persisted"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

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
            "active_session": self.state.load_session(),
        }


def _default_slice_factory(*, character_guid: int) -> Any:
    """Production default: hands character to SliceRuntime.bootstrap.

    Live applier wiring is left to the operator (separate config); the
    runtime returned here has the in-memory record-only compilers. Wire
    `wrap_with_live_compilers(rt, applier=...)` separately if/when the
    operator wants live apply.
    """
    from wm.cli.slice_demo import SliceRuntime
    return SliceRuntime.bootstrap(character_guid=character_guid,
                                  starter_item_entry=0)


def _default_slice_discoverer() -> int | None:
    """Production default: returns None — bootstrap requires an explicit GUID
    unless the operator wires a real spine discoverer at construction time.
    """
    return None


def serve(*, host: str = "127.0.0.1", port: int = 8765, state_root: Path | None = None,
          live_slice: bool = False, db_host: str = "127.0.0.1", db_port: int = 33307,
          db_user: str = "acore", db_password: str = "acore",
          world_db: str = "acore_world") -> None:
    state = PanelState(state_root) if state_root is not None else PanelState()
    state.ensure()
    slice_kwargs: dict[str, Any] = {}
    if live_slice:
        from wm.db.mysql_cli import MysqlCliClient
        from wm.llm.proposal_adapter import AdapterMode
        from wm.panel.slice_wiring import (
            SliceDbConfig,
            load_slice_quest_schema,
            make_live_marker_discoverer,
            make_live_slice_discoverer,
            make_live_slice_factory,
            make_live_slice_pump_factory,
        )
        client = MysqlCliClient()
        cfg = SliceDbConfig(host=db_host, port=db_port, user=db_user,
                            password=db_password, world_db=world_db)
        saved = state.load_settings()
        if not saved.get("model"):
            saved = {**saved, "model": "qwen3-coder-30b-a3b-instruct"}
        llm_client = LmStudioClient(LmStudioSettings.from_dict(saved))
        slice_kwargs = {
            "slice_factory": make_live_slice_factory(
                client=client, cfg=cfg,
                adapter_mode=AdapterMode.LIVE,
                llm_client=llm_client,
                quest_schema=load_slice_quest_schema()),
            "slice_discoverer": make_live_slice_discoverer(client=client, cfg=cfg),
            "slice_pump_factory": make_live_slice_pump_factory(client=client, cfg=cfg),
            "marker_discoverer": make_live_marker_discoverer(client=client, cfg=cfg),
        }
    app = PanelApp(state=state, **slice_kwargs)
    handler = _handler_for(app)
    server = ThreadingHTTPServer((host, int(port)), handler)
    print(f"WM panel listening on http://{host}:{int(port)}"
          + (" (live slice wiring on)" if live_slice else ""))
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


def _query_int(query: dict[str, list[str]], key: str, default: int) -> int:
    values = query.get(key) or []
    if not values or values[0] in (None, ""):
        return int(default)
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return int(default)


def _query_str(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key) or []
    if not values or values[0] in (None, ""):
        return None
    return str(values[0])


def _body_int(body: dict[str, Any], key: str, default: int) -> int:
    raw = body.get(key, default)
    if raw in (None, ""):
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _default_character_reader(player_guid: int) -> Any:
    from wm.character.reader import load_character_state
    from wm.config import Settings
    from wm.db.mysql_cli import MysqlCliClient
    return load_character_state(client=MysqlCliClient(), settings=Settings.from_env(), character_guid=int(player_guid))


def _session_from_marker_candidate(candidate: dict[str, Any], *, marker_spell_id: int) -> dict[str, Any]:
    guid = candidate.get("character_guid") or candidate.get("player_guid")
    if guid in (None, ""):
        return {}
    spell_id = candidate.get("spell_id") or marker_spell_id
    return {
        "character_guid": int(guid),
        "character_name": candidate.get("character_name") or candidate.get("player_name"),
        "source": "marker",
        "marker_spell_id": int(spell_id),
        "bridge_event_id": candidate.get("bridge_event_id"),
        "selected_at": utc_now_iso(),
        "marker": candidate,
    }


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
