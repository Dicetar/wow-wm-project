from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timezone
import json
import hashlib
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from wm.autoplay.ambient import build_ambient_messages
from wm.autoplay.ambient import classify_ambient_event
from wm.autoplay.ambient import HIGH_PRIORITY_AMBIENT_KINDS
from wm.autoplay._chat_text import _CHAT_PART_LIMIT
from wm.autoplay._chat_text import _CHAT_REPLY_MAX_CHARS
from wm.autoplay._chat_text import _chat_context_reset_payload
from wm.autoplay._chat_text import _chat_max_tokens
from wm.autoplay._chat_text import _fallback_chat_reply
from wm.autoplay._chat_text import _forget_context_ack
from wm.autoplay._chat_text import _guard_chat_reply
from wm.autoplay._chat_text import _is_forget_context_command
from wm.autoplay._chat_text import _sanitize_chat_reply
from wm.autoplay._chat_text import _split_chat_message
from wm.autoplay._chat_context import _chat_identity_facts
from wm.autoplay._chat_context import _deterministic_chat_fact_reply
from wm.autoplay._chat_context import _first_text
from wm.autoplay._chat_context import _looks_like_memory_statement
from wm.autoplay._chat_context import _looks_like_scene_request
from wm.autoplay._chat_context import _remembered_facts
from wm.autoplay._chat_context import _voice_world_digest
from wm.autoplay._compact import _applied_lane_counts
from wm.autoplay._compact import _as_list
from wm.autoplay._compact import _compact_draft_record
from wm.autoplay._compact import _compact_request
from wm.autoplay._compact import _draft_source_event_at
from wm.autoplay._compact import _int_or_none
from wm.autoplay._compact import _memory_revision
from wm.autoplay._compact import _parse_json_dict
from wm.autoplay._compact import _parse_time
from wm.autoplay._compact import _risk_from_payload
from wm.autoplay._compact import _stable_key
from wm.autoplay._publish_payloads import _entry_from_payload
from wm.autoplay._publish_payloads import _item_publish_payload_from_release
from wm.autoplay._publish_payloads import _quest_publish_payload_from_release
from wm.autoplay._publish_payloads import _quest_reward_payload
from wm.autoplay._publish_payloads import _spell_publish_payload_from_release
from wm.autoplay._runtime_plan import _execute_runtime_work
from wm.autoplay._runtime_plan import _runtime_action_proposal
from wm.autoplay._runtime_plan import _runtime_idempotency_keys
from wm.autoplay._runtime_plan import _runtime_proposals_from_draft
from wm.autoplay._runtime_plan import _runtime_publish_plan_from_draft
from wm.autoplay._runtime_plan import _runtime_results_ok
from wm.autoplay._runtime_plan import _runtime_rollback_available
from wm.autoplay._runtime_plan import _runtime_scene_proposals
from wm.autoplay._runtime_plan import _runtime_work_from_draft
from wm.autoplay._scene_helpers import _compact_chat_world_context
from wm.autoplay._scene_helpers import _compact_store_result
from wm.autoplay._scene_helpers import _dry_run_pending
from wm.autoplay._scene_helpers import _result_to_dict
from wm.autoplay._scene_helpers import _risk_from_proposal
from wm.autoplay._scene_helpers import _rollback_available
from wm.autoplay._scene_helpers import _scene_cleanup_status
from wm.autoplay._scene_helpers import _schema_from_proposal
from wm.autoplay._scene_helpers import _source_event_at
from wm.autoplay._runtime_status import _is_scoped_player_online
from wm.autoplay._runtime_status import _process_exists
from wm.autoplay._runtime_status import _read_pid
from wm.autoplay._runtime_status import _wow_client_running
from wm.autoplay._runtime_status import status_summary
from wm.autoplay.llm import AutoplayLlmAdapter
from wm.autoplay.llm import schema_for_lane
from wm.autoplay.policy import AutoplayPolicy
from wm.autoplay.policy import SafeWindow
from wm.autoplay.policy import SCHEMA_LANE
from wm.autoplay.state import AutoplayStateStore
from wm.autoplay.state import utc_now_iso
from wm.autoplay.tools import autoplay_tool_manifest
from wm.autoplay.world_context import build_chat_world_context
from wm.config import Settings
from wm.context.pack import build_session_context_pack
from wm.doctor import run_doctor
from wm.llm.lmstudio import LmStudioClient
from wm.llm.lmstudio import LmStudioSettings
from wm.llm.results import LlmResultError
from wm.llm.results import parse_json_object
from wm.panel.state import PanelState
from wm.runtime.markers import mark_runtime_service_stopped
from wm.runtime.markers import write_runtime_marker


DoctorFn = Callable[[Settings], list[Any]]


@dataclass(slots=True)
class AutoplayRuntimeConfig:
    player_guid: int | None = None
    interval_seconds: float = 2.0
    start_watcher: bool = True
    bridge_lab_mysql_port: int = 33307
    soap_port: int = 7879
    project_root: Path = Path.cwd()
    llm_enabled: bool = True
    llm_chat_enabled: bool = True
    llm_lanes: tuple[str, ...] = ("chat", "scene", "action")
    llm_event_age_seconds: int = 300
    llm_cooldown_seconds: int = 60
    llm_events_per_tick: int = 1
    llm_ambient_narration_enabled: bool = True
    llm_ambient_cooldown_seconds: int = 150
    llm_conversation_memory_enabled: bool = True
    llm_scene_director_enabled: bool = True
    durable_native_intent_enabled: bool = False
    durable_director_enabled: bool = False
    durable_director_player_guid: int | None = None
    initiative_preset: str = "moderate"
    activity_proposals_enabled: bool = True
    llm_model: str | None = None
    llm_base_url: str | None = None


@contextmanager
def _runtime_env_for_config(config: AutoplayRuntimeConfig):
    bridge_lab_root = config.project_root.parent / "WM_BridgeLab"
    bridge_config = bridge_lab_root / "run" / "configs" / "modules" / "mod_wm_bridge.conf"
    updates = {
        "WM_WORLD_DB_PORT": str(config.bridge_lab_mysql_port),
        "WM_CHAR_DB_PORT": str(config.bridge_lab_mysql_port),
        "WM_SOAP_PORT": str(config.soap_port),
        "WM_BRIDGELAB_DIR": str(bridge_lab_root),
        "WM_QUEST_GRANT_TRANSPORT": "auto",
    }
    if bridge_config.exists():
        updates["WM_BRIDGE_CONFIG_PATH"] = str(bridge_config)
    previous = {key: os.environ.get(key) for key in updates}
    try:
        os.environ.update(updates)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _settings_from_config(config: AutoplayRuntimeConfig) -> Settings:
    with _runtime_env_for_config(config):
        return Settings.from_env()


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
        # Health (LM Studio /v1/models) rarely changes; cache it per (base_url, model)
        # so the tick loop does not poll the model list every couple of seconds.
        self._llm_health_cache: dict[str, Any] | None = None
        self._activity_scan_at: dict[int, float] = {}

    def tick(self, *, config: AutoplayRuntimeConfig) -> dict[str, Any]:
        command = self.store.load_command()
        status = self.store.load_status()
        control_config = _merged_control_config(config=config, status=status, command=command)
        counters = dict(status.get("counters") or {})
        counters["ticks"] = int(counters.get("ticks") or 0) + 1

        stop_requested = bool(command.get("stop_requested") or status.get("stop_requested"))
        paused = bool(command.get("paused") or status.get("paused"))
        settings = _settings_from_config(config)
        readiness = self._readiness(settings)
        session = self._active_session(config=config)
        llm_enabled = bool(control_config.get("llm_enabled", True))
        llm = self._llm_health(control_config) if llm_enabled else _disabled_llm_status(control_config)
        safe_window = self._safe_window(settings=settings, session=session)
        generation_results: list[dict[str, Any]] = []
        apply_results: list[dict[str, Any]] = []
        if not stop_requested and not paused:
            generation_results = self._drive_llm_generation(
                control_config=control_config,
                settings=settings,
                readiness=readiness,
                session=session,
                llm=llm,
                status=status,
            )
            if generation_results:
                status = self.store.load_status()
                counters = dict(status.get("counters") or counters)
        if not stop_requested and not paused:
            apply_results = self._drive_validated_drafts(
                control_config=control_config,
                settings=settings,
                readiness=readiness,
                session=session,
                llm=llm,
                safe_window=safe_window,
                status=status,
            )
            if apply_results:
                status = self.store.load_status()
                counters = dict(status.get("counters") or counters)
        ambient_result: dict[str, Any] | None = None
        if not stop_requested and not paused and llm_enabled:
            ambient_result = self._drive_ambient_narration(
                control_config=control_config,
                settings=settings,
                readiness=readiness,
                session=session,
                llm=llm,
                status=status,
            )

        final_config = _merged_control_config(config=config, status=self.store.load_status(), command=self.store.load_command())
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
            "config": final_config,
            "policy": self.policy.to_dict(),
            "safe_window": safe_window.to_dict(),
            "latest_generation": generation_results[-1] if generation_results else status.get("latest_generation"),
            "latest_autoplay": apply_results[-1] if apply_results else status.get("latest_autoplay"),
            "latest_ambient": ambient_result if ambient_result is not None else status.get("latest_ambient"),
            "counters": counters,
        }
        return self.store.save_status(next_status)

    def run_forever(self, *, config: AutoplayRuntimeConfig, once: bool = False) -> int:
        marker_metadata = {
            "player_guid": config.player_guid,
            "lanes": list(_normalize_lanes(config.llm_lanes)),
            "once": bool(once),
        }
        existing_command = self.store.load_command()
        command_config = _config_to_dict(config)
        existing_config = existing_command.get("config") if isinstance(existing_command.get("config"), dict) else {}
        for key, value in existing_config.items():
            if command_config.get(key) in (None, "") and value not in (None, ""):
                command_config[key] = value
        panel_settings = self.panel_state.load_settings()
        if config.llm_model in (None, "") and panel_settings.get("model") not in (None, ""):
            command_config["llm_model"] = str(panel_settings["model"])
        if config.llm_base_url in (None, "") and panel_settings.get("base_url") not in (None, ""):
            command_config["llm_base_url"] = str(panel_settings["base_url"])
        self.store.save_command({
            "stop_requested": False,
            "paused": bool(existing_command.get("paused", False)),
            "config": command_config,
        })
        self.store.update_status(status="starting", running=True, paused=False, stop_requested=False, pid=os.getpid())
        write_runtime_marker(
            service="autoplay",
            command_key="wm.autoplay run",
            project_root=config.project_root,
            health="running",
            metadata=marker_metadata,
        )
        status: dict[str, Any] = {}
        try:
            if config.start_watcher and config.player_guid is not None:
                lanes = _normalize_lanes(config.llm_lanes)
                if lanes == ["chat"]:
                    self.store.append_journal(
                        "watcher_start",
                        {
                            "kind": "native_bridge",
                            "mode": "chat",
                            "status": "skipped",
                            "reason": "chat mode polls recent native bridge chat directly",
                        },
                    )
                else:
                    self._start_watcher(config)
            while True:
                write_runtime_marker(
                    service="autoplay",
                    command_key="wm.autoplay run",
                    project_root=config.project_root,
                    health="running",
                    metadata=marker_metadata,
                )
                status = self.tick(config=config)
                if once or status.get("stop_requested"):
                    break
                time.sleep(max(float(config.interval_seconds), 0.25))
            final_status = "stopped" if once or status.get("stop_requested") else status.get("status", "stopped")
            self.store.update_status(status=final_status, running=False)
            return 0
        finally:
            mark_runtime_service_stopped(
                service="autoplay",
                command_key="wm.autoplay run",
                project_root=config.project_root,
                metadata=marker_metadata,
            )

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

    def _llm_settings(self, control_config: dict[str, Any]) -> LmStudioSettings:
        saved = self.panel_state.load_settings()
        if control_config.get("llm_model"):
            saved = {**saved, "model": str(control_config["llm_model"])}
        if control_config.get("llm_base_url"):
            saved = {**saved, "base_url": str(control_config["llm_base_url"])}
        if not saved.get("model"):
            saved = {**saved, "model": "mistral-nemo-instruct-2407"}
        return LmStudioSettings.from_dict(saved)

    def _llm_adapter(self, control_config: dict[str, Any]) -> AutoplayLlmAdapter:
        return AutoplayLlmAdapter(client=LmStudioClient(self._llm_settings(control_config)))

    def _llm_health(self, control_config: dict[str, Any]) -> dict[str, Any]:
        ttl = float(control_config.get("llm_health_ttl_seconds") or 30.0)
        settings = self._llm_settings(control_config)
        cache_key = f"{settings.base_url}|{settings.model}"
        cache = self._llm_health_cache
        now = time.monotonic()
        if (
            cache is not None
            and cache.get("key") == cache_key
            and (now - float(cache.get("at") or 0.0)) < ttl
        ):
            return cache["value"]
        value = self._llm_adapter(control_config).health()
        self._llm_health_cache = {"key": cache_key, "at": now, "value": value}
        return value

    def _chat_reply(
        self,
        *,
        control_config: dict[str, Any],
        player_guid: int,
        message: str,
        world_context: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        settings = self._llm_settings(control_config)
        player_message = str(message)[:1000]
        chat_context = world_context or {
            "schema_version": "wm.autoplay.chat_world_context.v1",
            "speaker": {"guid": int(player_guid), "message": player_message},
            "notes": ["minimal_context: no DB snapshot supplied"],
        }
        if "author_notes" not in chat_context:
            chat_context = dict(chat_context, author_notes=self.panel_state.author_notes.context(int(player_guid)))
        context_reset = _chat_context_reset_payload(control_config)
        identity = _chat_identity_facts(chat_context, player_guid=int(player_guid))
        deterministic_reply = _deterministic_chat_fact_reply(player_message, identity=identity)
        if deterministic_reply:
            return {
                "message": deterministic_reply,
                "raw_content": deterministic_reply,
                "source": "deterministic_fact",
                "model": settings.model,
            }
        manifest = autoplay_tool_manifest(modes=control_config.get("conversational_verb_modes"))
        # Second pass: a schema-bound classifier decides whether to emit a typed verb.
        # The roleplay voice almost never tool-calls, so this is the real action path.
        # Built before the voice client so the voice client is constructed last.
        extracted_intent = self._extract_chat_intent(
            control_config=control_config,
            settings=settings,
            player_guid=int(player_guid),
            message=player_message,
            identity=identity,
            manifest=manifest,
            author_notes=chat_context.get("author_notes"),
        )
        # LM Studio's json_schema channel is model/backend-sensitive; direct chat is
        # short and low-risk, so use text mode and sanitize the plain answer.
        client = LmStudioClient(replace(settings, schema_mode="text", max_tokens=_chat_max_tokens(settings)))
        attempts = [
            [
                {
                    "role": "system",
                    "content": (
                        "You are World Master, speaking inside the game. Reply in plain in-game chat prose, at most "
                        "a few short sentences. No markdown, bullets, headings, or quotes. "
                        "No erotic, sexual, or fetish roleplay. Keep the tone suitable for an in-game fantasy world. "
                        "Your real powers (healing, granting money or items, casting, summoning, and more) are carried "
                        "out by a separate action system that runs automatically when the player clearly asks. So never "
                        "tell the player you cannot do something, that you lack the power, or that they must go to a "
                        "merchant, healer, or trainer instead -- answer in character and let the action system handle it. "
                        "Do not announce the mechanical outcome yourself; a separate confirmation is sent. Never state or "
                        "imply that an action has already happened -- that you have healed, granted, summoned, spawned, "
                        "taught, cast, or completed anything. Speak only as acknowledgement or anticipation (e.g. 'Very "
                        "well, let it be so') and let the separate confirmation report what truly occurred. If you are "
                        "unsure something is possible, respond warmly without committing to a specific mechanical result. "
                        "The authoritative player identity is supplied separately; use exact names and GUIDs from it. "
                        "For location, use only authoritative_player_identity (map/zone/area IDs, names, and position). "
                        "Never invent zone or place names; only use zone_name/area_name if present in the identity (these "
                        "are authoritative from the game), otherwise give the numeric IDs and coordinates. If location_fresh "
                        "is not true, say you have not sensed the live position yet rather than guessing. "
                        "authoritative_player_identity.remembered lists durable facts you have learned about this player "
                        "across sessions (preferences, how they want to be addressed, likes/dislikes). Honor them naturally; "
                        "do not recite them verbatim or claim to remember things not listed there. "
                        "world_context.perception gives only ambient counts of nearby creatures and objects, refreshed slowly. "
                        "It tells you whether things are around, not what they are. Do not invent specific nearby creatures or "
                        "objects from it. When the moment actually calls for it, look closer by issuing the context_snapshot_request "
                        "verb; do not request a snapshot every message. "
                        "Never invent, translate, autocorrect, or rename the player. Do not think. Do not explain. "
                        "You may also include one optional action. Respond ONLY as a JSON object: "
                        '{"reply": "<a short in-game reply, a few sentences at most>", "intent": null} '
                        'or, to act, set "intent" to {"verb": "<one kind from wm_tools.native_actions>", '
                        '"args": {...}, "reason": "<why>"}. Choose a verb only if the player clearly wants it. '
                        "If unsure, set intent to null."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "player_guid": int(player_guid),
                            "channel": "wm_chat",
                            "player_message": player_message,
                            "authoritative_player_identity": identity,
                            "chat_context_reset": context_reset,
                            # Trimmed: the voice only needs identity + a light ambient
                            # summary. The full world_context and the verb manifest are
                            # for the separate intent extractor; sending them here just
                            # bloated prefill and slowed every reply.
                            "world_context": _voice_world_digest(chat_context),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
            [
                {
                    "role": "system",
                    "content": "Reply as World Master in plain prose, a few short sentences at most. Do not think. Do not explain.",
                },
                {
                    "role": "user",
                    "content": f"Player {int(player_guid)} says: {player_message}",
                },
            ],
        ]
        if chat_context.get("author_notes"):
            from wm.author_notes import NOTE_RULES
            for attempt in attempts:
                attempt[0]["content"] += " " + NOTE_RULES
            attempts[-1][-1]["content"] += "\nauthor_notes: " + json.dumps(
                chat_context["author_notes"], ensure_ascii=False)
        if chat_context.get("world_read"):
            read_instruction = (
                " This is an information-only request. Answer using world_context.world_read results: "
                "existing names, IDs and source coordinates from that tool may be quoted. They are database "
                "ingredients, not guaranteed living actors, accessible terrain, certain drops or deployed spell behavior. "
                "State relevant unknowns briefly. If status is ambiguous, ask which returned item is intended. "
                "If no match was found, say so. Do not acknowledge a grant or invent an offer. Set intent to null."
            )
            for attempt in attempts:
                attempt[0]["content"] += read_instruction
            attempts[-1][-1]["content"] += "\nworld_context: " + json.dumps(
                {"world_read": chat_context["world_read"]}, ensure_ascii=False,
            )
        last_error: Exception | None = None
        for messages in attempts:
            try:
                result = client.generate_text(messages=messages)
            except Exception as exc:
                last_error = exc
                continue
            content = str(result.get("content") or "").strip()
            reply = content
            try:
                parsed = parse_json_object(content)
            except LlmResultError:
                parsed = {}
            if isinstance(parsed, dict):
                text = parsed.get("reply")
                if text in (None, ""):
                    text = parsed.get("message")
                if text not in (None, ""):
                    reply = str(text).strip()
            reply = _sanitize_chat_reply(reply)
            reply = _guard_chat_reply(reply)
            intent = None
            if isinstance(parsed, dict) and isinstance(parsed.get("intent"), dict):
                raw = parsed["intent"]
                verb = str(raw.get("verb") or "").strip()
                if verb:
                    intent = {
                        "verb": verb,
                        "args": raw.get("args") if isinstance(raw.get("args"), dict) else {},
                        "reason": str(raw.get("reason") or "")[:300],
                    }
            if reply:
                selected_intent = extracted_intent if control_config.get("durable_director_enabled") else (extracted_intent or intent)
                return {"message": reply, "raw_content": content, "source": "llm",
                        "model": settings.model, "intent": selected_intent}
            last_error = RuntimeError("LM Studio response message content was empty.")
        if last_error is not None:
            fallback = _fallback_chat_reply(str(last_error))
            return {
                "message": fallback,
                "raw_content": "",
                "source": "llm_fallback",
                "model": settings.model,
                "error": str(last_error),
                "intent": extracted_intent,
            }
        fallback = _fallback_chat_reply("LM Studio did not return a chat message.")
        return {
            "message": fallback,
            "raw_content": "",
            "source": "llm_fallback",
            "model": settings.model,
            "error": "LM Studio did not return a chat message.",
            "intent": extracted_intent,
        }

    def _extract_chat_intent(
        self,
        *,
        control_config: dict[str, Any],
        settings: LmStudioSettings,
        player_guid: int,
        message: str,
        identity: dict[str, Any],
        manifest: dict[str, Any],
        author_notes: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if control_config.get("durable_director_enabled"):
            return None
        if not control_config.get("llm_intent_enabled", True):
            return None
        try:
            from wm.autoplay.intent_extract import build_intent_client
            from wm.autoplay.intent_extract import extract_chat_intent

            client = build_intent_client(LmStudioClient, settings, control_config=control_config)
            return extract_chat_intent(
                client=client,
                player_guid=int(player_guid),
                message=message,
                manifest=manifest,
                identity=identity,
                author_notes=author_notes,
            )
        except Exception:
            return None

    def _handle_author_note(self, *, settings: Settings, player_guid: int, message: str,
                           source_event: dict[str, Any] | None) -> dict[str, Any] | None:
        if message.strip().partition(" ")[0].casefold() not in {"/note", "/note!", "/notes"}:
            return None
        origin = str((source_event or {}).get("source_event_key") or (source_event or {}).get("event_id") or "")
        try:
            result = self.panel_state.author_notes.command(
                message, player_guid=player_guid, source="wm_chat" if source_event else "operator_chat",
                origin_key=f"note:{player_guid}:{origin}" if origin else None)
        except ValueError as exc:
            result = {"ok": False, "message": f"Author's Note not saved: {exc}"}
        except Exception as exc:
            self.store.add_issue({"reason": "author_notes_unavailable", "kind": "memory", "detail": str(exc)[:500]})
            return {"ok": False, "error": "author_notes_unavailable", "retryable": True}
        sent = self._send_chat_reply(
            settings=settings, player_guid=player_guid, source_message=message,
            reply={"message": result["message"], "raw_content": result["message"], "source": "author_note_command"},
            source_event=source_event, world_context=None)
        return {**sent, "author_note": result}

    def _chat_world_context(
        self,
        *,
        settings: Settings,
        player_guid: int,
        message: str,
        source_event: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            context = build_chat_world_context(
                settings=settings,
                player_guid=int(player_guid),
                message=message,
                source_event=source_event,
            )
        except Exception as exc:
            context = {
                "schema_version": "wm.autoplay.chat_world_context.v1",
                "speaker": {"guid": int(player_guid), "message": str(message)[:1000]},
                "source_event": source_event,
                "notes": [f"world_context_failed: {type(exc).__name__}: {exc}"],
            }
        context["author_notes"] = self.panel_state.author_notes.context(int(player_guid))
        return context

    def _decide_director_chat(
        self, *, control_config: dict[str, Any], player_guid: int,
        message: str, world_context: dict[str, Any], source_key: str,
        source_event_at: str | None, proactive: bool = False,
    ) -> Any:
        from wm.autoplay.decision import decide_request
        from wm.autoplay.director_intake import DirectorIntakeLedger
        from wm.autoplay.activities import compact_activity_context

        settings = replace(self._llm_settings(control_config), schema_mode="json_schema", max_tokens=256)
        context_pack = world_context.get("session_context_pack") or {}
        evidence = {
            "observed_at": source_event_at or utc_now_iso(),
            "selected_character": _chat_identity_facts(world_context, player_guid=player_guid),
            "player_request": message[:1000],
            "world_facts": {
                "live_location": world_context.get("live_location"),
                "perception": world_context.get("perception"),
                "activities": compact_activity_context(world_context.get("activities") or {}),
            },
            "obligations": (world_context.get("database") or {}).get("active_quests", [])[:20],
            "author_notes": world_context.get("author_notes") or self.panel_state.author_notes.context(player_guid),
            "narrative_memory": (context_pack.get("memory") or [])[:10],
            "capabilities": ["material_delivery"] if proactive else ["quest", "material_delivery", "world_announce_to_player", "world_scout", "world_lookup", "loot_sources"],
            "initiative": {"proactive": proactive, "preset": control_config.get("initiative_preset", "moderate")},
        }
        intake_ledger = DirectorIntakeLedger(settings=Settings.from_env())
        intake = intake_ledger.prepare(
            origin_key=f"director:decision:{source_key}", player_guid=player_guid, evidence=evidence,
        )
        if intake.decision is not None:
            return intake.decision
        decision = decide_request(client=LmStudioClient(settings), evidence=intake.evidence)
        return intake_ledger.decide(intake, decision=decision)

    def generate_once(
        self,
        *,
        config: AutoplayRuntimeConfig,
        lane: str | None = None,
        event_id: int | None = None,
        source_event_key: str | None = None,
    ) -> dict[str, Any]:
        command = self.store.load_command()
        status = self.store.load_status()
        control_config = _merged_control_config(config=config, status=status, command=command)
        if lane:
            control_config["llm_lanes"] = [str(lane)]
        settings = _settings_from_config(config)
        readiness = self._readiness(settings)
        session = self._active_session(config=config)
        llm = self._llm_health(control_config)
        if event_id is not None or source_event_key:
            event = self._load_event(settings=settings, event_id=event_id, source_event_key=source_event_key)
            if event is None:
                return {"ok": False, "error": "event not found"}
            opportunity = _opportunity_from_event(
                event=event,
                lanes=_normalize_lanes(control_config.get("llm_lanes")),
                max_event_age_seconds=int(control_config.get("llm_event_age_seconds") or 300),
                force_lane=lane,
            )
            if opportunity is None:
                return {"ok": False, "error": "event is not eligible for enabled lanes"}
            result = self._generate_for_opportunity(
                control_config=control_config,
                settings=settings,
                readiness=readiness,
                session=session,
                llm=llm,
                opportunity=opportunity,
            )
            return {"ok": bool(result.get("ok")), "result": result}
        results = self._drive_llm_generation(
            control_config=control_config,
            settings=settings,
            readiness=readiness,
            session=session,
            llm=llm,
            status=status,
            force_lane=lane,
            ignore_cooldown=True,
        )
        return {"ok": bool(results), "results": results}

    def chat_once(
        self,
        *,
        config: AutoplayRuntimeConfig,
        message: str,
    ) -> dict[str, Any]:
        command = self.store.load_command()
        status = self.store.load_status()
        control_config = _merged_control_config(config=config, status=status, command=command)
        settings = _settings_from_config(config)
        readiness = self._readiness(settings)
        session = self._active_session(config=config)
        llm = self._llm_health(control_config)
        if not readiness.get("ok"):
            return {"ok": False, "error": "readiness_not_green", "readiness": readiness}
        if not session or session.get("character_guid") in (None, ""):
            return {"ok": False, "error": "no_active_session"}
        player_guid = int(session["character_guid"])
        if control_config.get("durable_director_enabled") and int(control_config.get("durable_director_player_guid") or 0) != player_guid:
            return {"ok": False, "error": "director_scope_mismatch"}
        note_result = self._handle_author_note(
            settings=settings, player_guid=player_guid, message=message, source_event=None)
        if note_result is not None:
            return note_result
        if not llm.get("ok"):
            return {"ok": False, "error": "llm_unavailable", "llm": llm}
        resolved = None if control_config.get("durable_director_enabled") else self._resolve_pending_if_yes_no(
            settings=settings, control_config=control_config, player_guid=player_guid, message=message)
        if resolved is not None:
            return {"ok": True, "pending_resolution": resolved}
        if _is_forget_context_command(message):
            status = self.store.reset_chat_context(actor_guid=player_guid, source="chat_cli")
            reply = {
                "message": _forget_context_ack(status),
                "raw_content": _forget_context_ack(status),
                "source": "context_reset",
                "model": (control_config.get("llm_model") or llm.get("model")),
            }
            return self._send_chat_reply(
                settings=settings,
                player_guid=player_guid,
                source_message=message,
                reply=reply,
                source_event=None,
                world_context=None,
            )
        world_context = self._chat_world_context(
            settings=settings,
            player_guid=player_guid,
            message=message,
            source_event=None,
        )
        try:
            if control_config.get("durable_director_enabled"):
                decision = self._decide_director_chat(
                    control_config=control_config, player_guid=player_guid, message=message,
                    world_context=world_context, source_key=f"operator-chat:{player_guid}:{time.time_ns()}",
                    source_event_at=utc_now_iso(),
                )
                if decision.outcome == "inspect_world":
                    return self._reply_with_world_read(
                        decision=decision, control_config=control_config, settings=settings,
                        player_guid=player_guid, message=message, world_context=world_context, source_event=None,
                    )
            reply = self._chat_reply(
                control_config=control_config,
                player_guid=player_guid,
                message=message,
                world_context=world_context,
            )
        except Exception as exc:
            issue = self.store.add_issue({
                "reason": "chat_reply_failed",
                "kind": "chat",
                "detail": str(exc)[:1000],
                "payload": {"message": str(message)[:1000], "player_guid": player_guid},
            })
            return {"ok": False, "error": "reply_failed", "issue": _compact_store_result(issue)}
        send_result = self._send_chat_reply(
            settings=settings,
            player_guid=player_guid,
            source_message=message,
            reply=reply,
            source_event=None,
            world_context=world_context,
        )
        scene_result = None
        if not control_config.get("durable_director_enabled") and _looks_like_scene_request(message):
            scene_result = self._handle_scene_request(
                settings=settings, control_config=control_config, player_guid=player_guid,
                message=message, world_context=world_context)
        if scene_result is not None:
            send_result["scene_result"] = scene_result
        elif reply.get("intent"):
            send_result["intent_result"] = self._handle_intent(
                settings=settings, control_config=control_config, player_guid=player_guid,
                intent=reply["intent"], source_message=message)
        self._capture_conversation_memory(
            control_config=control_config, settings=settings, player_guid=player_guid,
            message=message, world_context=world_context)
        return send_result

    def _reply_to_chat_event(
        self,
        *,
        control_config: dict[str, Any],
        settings: Settings,
        session: dict[str, Any] | None,
        event_payload: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = event_payload.get("metadata") if isinstance(event_payload.get("metadata"), dict) else {}
        message = str(event_payload.get("event_value") or metadata.get("message") or "").strip()
        player_guid_value = event_payload.get("player_guid") or (session or {}).get("character_guid")
        source_key = str(event_payload.get("source_event_key") or event_payload.get("event_id") or "")
        base_result = {
            "ok": False,
            "lane": "chat",
            "source_event_key": source_key,
            "player_guid": player_guid_value,
        }
        if player_guid_value in (None, ""):
            issue = self.store.add_issue({
                "reason": "chat_missing_player_guid",
                "kind": "chat",
                "payload": {"source_event": event_payload},
            })
            return {**base_result, "error": "missing_player_guid", "issue": _compact_store_result(issue)}
        player_guid = int(player_guid_value)
        if not message:
            issue = self.store.add_issue({
                "reason": "chat_missing_message",
                "kind": "chat",
                "payload": {"source_event": event_payload},
            })
            return {**base_result, "error": "missing_message", "issue": _compact_store_result(issue)}
        director_enabled = bool(control_config.get("durable_director_enabled"))
        if director_enabled and int(control_config.get("durable_director_player_guid") or 0) != player_guid:
            return {**base_result, "error": "director_scope_mismatch"}
        note_result = self._handle_author_note(
            settings=settings, player_guid=player_guid, message=message, source_event=event_payload)
        if note_result is not None:
            return {**base_result, **note_result}
        resolved = None if director_enabled else self._resolve_pending_if_yes_no(
            settings=settings, control_config=control_config, player_guid=player_guid, message=message)
        if resolved is not None:
            return {**base_result, "ok": True, "lane": "chat", "source_event_key": source_key,
                    "pending_resolution": resolved}
        if _is_forget_context_command(message):
            status = self.store.reset_chat_context(actor_guid=player_guid, source="wm_chat")
            reply = {
                "message": _forget_context_ack(status),
                "raw_content": _forget_context_ack(status),
                "source": "context_reset",
                "model": control_config.get("llm_model"),
            }
            result = self._send_chat_reply(
                settings=settings,
                player_guid=player_guid,
                source_message=message,
                reply=reply,
                source_event=event_payload,
                world_context=None,
            )
            return {**base_result, **result, "lane": "chat", "source_event_key": source_key}

        world_context = self._chat_world_context(
            settings=settings,
            player_guid=player_guid,
            message=message,
            source_event=event_payload,
        )
        decision = None
        if director_enabled:
            try:
                decision = self._decide_director_chat(
                    control_config=control_config, player_guid=player_guid,
                    message=message, world_context=world_context, source_key=source_key,
                    source_event_at=event_payload.get("occurred_at"),
                )
            except Exception as exc:
                self.store.add_issue({"reason": "director_decision_unavailable", "kind": "decision",
                                      "detail": str(exc)[:500], "payload": {"source_event_key": source_key}})
            if decision is None:
                return {**base_result, "error": "director_decision_unavailable", "retryable": True}
            result: dict[str, Any] = {"ok": True, "decision": decision.outcome}
            try:
                if decision.outcome == "inspect_world":
                    result.update(self._reply_with_world_read(
                        decision=decision, control_config=control_config, settings=settings,
                        player_guid=player_guid, message=message, world_context=world_context,
                        source_event=event_payload,
                    ))
                elif decision.outcome == "propose_content":
                    opportunity = {
                        "opportunity_id": f"director-quest-{source_key}", "stable_key": source_key,
                        "source_event_key": source_key, "source_event_at": event_payload.get("occurred_at"),
                        "source_event": event_payload, "lane": "quest",
                        "schema_version": "wm.quest.release.material_delivery.v1" if decision.capability == "material_delivery" else schema_for_lane("quest"), "player_guid": player_guid,
                        "player_request": message[:1000], "risk": "low",
                    }
                    result["content_result"] = self._generate_for_opportunity(
                        control_config=control_config, settings=settings, readiness={"ok": True},
                        session={"character_guid": player_guid}, llm={"ok": True},
                        opportunity=opportunity,
                    )
                    if not result["content_result"].get("ok"):
                        result["ok"] = False
                        result["retryable"] = bool(result["content_result"].get("retryable"))
                elif decision.outcome in {"propose_action", "ask_clarification"}:
                    announcement = decision.args if decision.outcome == "propose_action" else {"message": decision.question}
                    result["intent_result"] = self._handle_intent(
                        settings=settings, control_config=control_config, player_guid=player_guid,
                        intent={"verb": "world_announce_to_player", "args": announcement,
                                "reason": decision.reason},
                        source_message=message, source_event_key=source_key,
                        source_event_at=event_payload.get("occurred_at"),
                    )
                    if result["intent_result"].get("intent") == "unavailable":
                        result["ok"] = False
                        result["retryable"] = True
                elif decision.outcome == "needs_capability":
                    from wm.autoplay.director_intake import DirectorIntakeLedger

                    result["development_task"] = DirectorIntakeLedger(settings=settings).await_capability(
                        origin_key=f"director:decision:{source_key}", player_guid=player_guid,
                        request=message, capability=decision.capability, reason=decision.reason,
                    )
                self._capture_conversation_memory(
                    control_config=control_config, settings=settings, player_guid=player_guid,
                    message=message, world_context=world_context,
                )
                return {**base_result, **result}
            except Exception as exc:
                self.store.add_issue({"reason": "director_chat_failed", "kind": "decision",
                                      "detail": str(exc)[:500], "payload": {"source_event_key": source_key}})
                return {**base_result, "error": "director_chat_failed", "retryable": True}
        try:
            reply = self._chat_reply(
                control_config=control_config,
                player_guid=player_guid,
                message=message,
                world_context=world_context,
            )
            result = self._send_chat_reply(
                settings=settings,
                player_guid=player_guid,
                source_message=message,
                reply=reply,
                source_event=event_payload,
                world_context=world_context,
            )
            scene_result = None
            if not director_enabled and _looks_like_scene_request(message):
                scene_result = self._handle_scene_request(
                    settings=settings, control_config=control_config, player_guid=player_guid,
                    message=message, world_context=world_context)
            if scene_result is not None:
                result["scene_result"] = scene_result
            elif reply.get("intent"):
                result["intent_result"] = self._handle_intent(
                    settings=settings, control_config=control_config, player_guid=player_guid,
                    intent=reply["intent"], source_message=message, source_event_key=source_key)
            self._capture_conversation_memory(
                control_config=control_config, settings=settings, player_guid=player_guid,
                message=message, world_context=world_context)
            return {**base_result, **result, "lane": "chat", "source_event_key": source_key}
        except Exception as exc:
            issue = self.store.add_issue({
                "reason": "chat_reply_failed",
                "kind": "chat",
                "detail": str(exc)[:1000],
                "payload": {"source_event": event_payload, "message": message},
            })
            return {**base_result, "error": "reply_failed", "issue": _compact_store_result(issue)}

    def _reply_with_world_read(
        self, *, decision: Any, control_config: dict[str, Any], settings: Settings,
        player_guid: int, message: str, world_context: dict[str, Any], source_event: dict[str, Any] | None,
    ) -> dict[str, Any]:
        from wm.world.ingredients import compact_read_result, execute_read_tool

        observed = execute_read_tool(capability=decision.capability, args=decision.args,
                                     player_guid=player_guid, settings=settings)
        world_context = dict(world_context, world_read={
            "capability": decision.capability, "arguments": decision.args,
            "observed_at": utc_now_iso(), "result": compact_read_result(observed),
        })
        reply = self._chat_reply(control_config=control_config, player_guid=player_guid,
                                 message=message, world_context=world_context)
        # Information retrieval must not opportunistically execute an unrelated voice intent.
        reply.pop("intent", None)
        sent = self._send_chat_reply(settings=settings, player_guid=player_guid,
                                    source_message=message, reply=reply, source_event=source_event,
                                    world_context=world_context)
        return {**sent, "world_read": world_context["world_read"]}

    def _send_chat_reply(
        self,
        *,
        settings: Settings,
        player_guid: int,
        source_message: str,
        reply: dict[str, Any],
        source_event: dict[str, Any] | None,
        world_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        parts, ok, results = self._dispatch_chat_parts(
            settings=settings, player_guid=player_guid,
            message=str(reply["message"]), source_message=source_message,
        )
        record = {
            "at": utc_now_iso(),
            "player_guid": int(player_guid),
            "message": str(source_message),
            "reply": reply,
            "source_event": source_event,
            "world_context": _compact_chat_world_context(world_context) if world_context is not None else None,
            "parts": parts,
            "part_results": results,
            "dry_run": results[0]["dry_run"] if results else None,
            "apply": results[-1]["apply"] if results else None,
        }
        if not parts:
            issue = self.store.add_issue({"reason": "chat_empty_reply", "kind": "chat", "payload": record})
            return {"ok": False, "error": "empty_reply", "issue": _compact_store_result(issue), "reply": reply}
        failed = next((r for r in results if r.get("stage") == "dry_run"), None)
        if failed is not None:
            issue = self.store.add_issue({"reason": "chat_dry_run_failed", "kind": "chat", "payload": record})
            return {"ok": False, "error": "dry_run_failed", "issue": _compact_store_result(issue), "reply": reply}
        self.store.append_journal("chat", record)
        current = self.store.load_status()
        counters = dict(current.get("counters") or {})
        counters["chat_replies"] = int(counters.get("chat_replies") or 0) + 1
        self.store.update_status(counters=counters, latest_chat=record)
        if not ok:
            issue = self.store.add_issue({"reason": "chat_apply_failed", "kind": "chat", "payload": record})
            return {"ok": False, "error": "apply_failed", "issue": _compact_store_result(issue), "reply": reply}
        return {"ok": True, "reply": reply, "parts": parts, "apply": record["apply"]}

    def _resolve_pending_if_yes_no(
        self,
        *,
        settings: Settings,
        control_config: dict[str, Any],
        player_guid: int,
        message: str,
    ) -> dict[str, Any] | None:
        from wm.autoplay.intent import is_affirmation, is_negation

        pending = self.store.load_pending_intent(player_guid)
        if not pending:
            return None
        if is_negation(message):
            self.store.clear_pending_intent(player_guid, reason="player_declined")
            self._audit_intent(
                player_guid=player_guid,
                verb=str(pending.get("verb") or "action"),
                outcome="declined",
                source_message=message,
                reason="player_declined",
                mode=str(pending.get("mode") or "confirm"),
            )
            self._speak(settings=settings, player_guid=player_guid,
                        text="Understood, I will hold off.", source_message=message)
            return {"intent": "declined", "verb": pending.get("verb")}
        if is_affirmation(message):
            return self._apply_pending(settings=settings, player_guid=player_guid,
                                       pending=pending, source_message=message)
        # ambiguous reply -> drop the stale pending and let normal handling proceed
        self.store.clear_pending_intent(player_guid, reason="superseded")
        return None

    def _handle_intent(
        self,
        *,
        settings: Settings,
        control_config: dict[str, Any],
        player_guid: int,
        intent: dict[str, Any],
        source_message: str,
        source_event_key: str | None = None,
        source_event_at: str | None = None,
    ) -> dict[str, Any]:
        from wm.autoplay.intent import IntentRejection, compile_intent, intent_failure_message

        verb = str(intent.get("verb") or "")
        intent_args = intent.get("args") if isinstance(intent.get("args"), dict) else {}
        if control_config.get("durable_director_enabled") and verb != "world_announce_to_player":
            return {"intent": "unavailable", "verb": verb, "reason": "director_capability_unsupported"}

        # creature_spawn needs a numeric creature_entry the model cannot supply.
        # Resolve the spoken creature name to an entry deterministically; the
        # native verb spawns it near the player on its own.
        if verb == "creature_spawn":
            from wm.autoplay.spawn_args import SpawnArgsError, prepare_creature_spawn_args
            from wm.targets.name_resolver import get_default_creature_name_resolver

            prepared = prepare_creature_spawn_args(
                intent_args, resolver=get_default_creature_name_resolver()
            )
            if isinstance(prepared, SpawnArgsError):
                self._audit_intent(
                    player_guid=player_guid,
                    verb=verb,
                    outcome="rejected",
                    source_message=source_message,
                    reason=prepared.reason,
                    intent=intent,
                )
                self.store.add_issue({
                    "reason": "spawn_args_unresolved", "kind": "intent",
                    "detail": prepared.reason,
                    "payload": {"intent": intent, "player_guid": int(player_guid)},
                })
                message = intent_failure_message(reason=prepared.reason, verb=verb)
                self._speak(settings=settings, player_guid=player_guid,
                            text=message,
                            source_message=source_message)
                return {"intent": "rejected", "reason": prepared.reason, "player_message": message}
            intent_args = prepared

        compiled = compile_intent(
            player_guid=player_guid,
            verb=verb,
            args=intent_args,
            modes=control_config.get("conversational_verb_modes"),
            reason=str(intent.get("reason") or ""),
            origin_key=source_event_key,
        )
        if isinstance(compiled, IntentRejection):
            self._audit_intent(
                player_guid=player_guid,
                verb=verb,
                outcome="rejected",
                source_message=source_message,
                reason=compiled.reason,
                intent=intent,
            )
            self.store.add_issue({
                "reason": "intent_rejected", "kind": "intent",
                "detail": compiled.reason,
                "payload": {"intent": intent, "player_guid": int(player_guid)},
            })
            message = intent_failure_message(reason=compiled.reason, verb=verb)
            if not control_config.get("durable_director_enabled"):
                self._speak(settings=settings, player_guid=player_guid, text=message, source_message=source_message)
            return {"intent": "rejected", "reason": compiled.reason, "player_message": message}
        coordinator = self._control_coordinator(settings)
        dry = coordinator.execute(proposal=compiled.proposal, mode="dry-run", confirm_live_apply=False)
        if dry.status != "dry-run":
            self._audit_intent(
                player_guid=player_guid,
                verb=compiled.verb,
                outcome="dry_run_failed",
                source_message=source_message,
                reason=str(_result_to_dict(dry)),
                mode=compiled.mode,
                risk=compiled.risk,
            )
            self.store.add_issue({
                "reason": "intent_dry_run_failed", "kind": "intent",
                "detail": _result_to_dict(dry), "payload": {"verb": compiled.verb},
            })
            message = intent_failure_message(reason=str(_result_to_dict(dry)), verb=compiled.verb)
            if not control_config.get("durable_director_enabled"):
                self._speak(settings=settings, player_guid=player_guid, text=message, source_message=source_message)
            return {"intent": "dry_run_failed", "verb": compiled.verb, "player_message": message}
        if compiled.mode == "auto":
            if compiled.verb == "world_announce_to_player" and control_config.get("durable_director_enabled"):
                if int(control_config.get("durable_director_player_guid") or 0) != int(player_guid):
                    return {"intent": "unavailable", "verb": compiled.verb, "reason": "director_scope_mismatch"}
                return self._apply_durable_director_intent(
                    settings=settings, player_guid=player_guid, compiled=compiled,
                    source_event_key=source_event_key, source_message=source_message, dry_run=dry,
                    source_event_at=source_event_at,
                )
            if compiled.verb == "world_announce_to_player" and control_config.get("durable_native_intent_enabled"):
                return self._apply_durable_native_intent(
                    settings=settings, player_guid=player_guid, compiled=compiled,
                    source_event_key=source_event_key, source_message=source_message,
                )
            return self._apply_compiled(settings=settings, player_guid=player_guid,
                                        compiled=compiled, source_message=source_message)
        if control_config.get("durable_director_enabled"):
            if not source_event_key or not source_event_at:
                return {"intent": "unavailable", "verb": compiled.verb, "reason": "director_confirmation_unsupported"}
            from wm.autoplay.director_work import DirectorWorkLedger, FrozenWork

            artifact = FrozenWork.from_runtime({"kind": "control", "proposals": [compiled.proposal]})
            work = DirectorWorkLedger(settings=settings).prepare(
                origin_key=f"wm_chat:{player_guid}:{source_event_key}", player_guid=player_guid,
                lane="action", artifact=artifact, preview=dry.to_dict(),
                evidence={"source_event_key": source_event_key, "message": source_message[:1000],
                          "schema_version": "control.proposal.v1", "risk": compiled.risk,
                          "source_event_at": source_event_at},
            )
            return {"intent": "awaiting_approval", "verb": compiled.verb,
                    "request_id": work.request_id, "artifact_hash": work.artifact_hash}
        # confirm mode -> park pending, surfaced in chat + panel inbox (same record)
        self.store.set_pending_intent(player_guid, {
            "verb": compiled.verb,
            "risk": compiled.risk,
            "mode": compiled.mode,
            "summary": intent.get("reason") or compiled.verb,
            "proposal": compiled.proposal.model_dump(mode="json"),
        }, ttl_seconds=120)
        self._audit_intent(
            player_guid=player_guid,
            verb=compiled.verb,
            outcome="pending_confirmation",
            source_message=source_message,
            reason=str(intent.get("reason") or compiled.verb),
            mode=compiled.mode,
            risk=compiled.risk,
        )
        self._speak(settings=settings, player_guid=player_guid,
                    text=f"I can {compiled.verb.replace('_', ' ')} - say yes to confirm.",
                    source_message=source_message)
        return {"intent": "pending", "verb": compiled.verb}

    def _audit_intent(
        self,
        *,
        player_guid: int,
        verb: str,
        outcome: str,
        source_message: str,
        reason: str | None = None,
        mode: str | None = None,
        risk: str | None = None,
        intent: dict[str, Any] | None = None,
        verification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "schema_version": "wm.autoplay.intent_audit.v1",
            "player_guid": int(player_guid),
            "verb": str(verb or "action"),
            "outcome": str(outcome),
            "source_message": str(source_message or "")[:500],
            "reason": str(reason or "")[:500],
            "mode": mode,
            "risk": risk,
            "intent": _compact_intent(intent),
            "verification": verification,
        }
        return self.store.append_journal("intent_audit", record)

    def _capture_conversation_memory(
        self,
        *,
        control_config: dict[str, Any],
        settings: Settings,
        player_guid: int,
        message: str,
        world_context: dict[str, Any] | None,
    ) -> None:
        """Phase 4: persist a durable fact the player stated, if any.

        Best-effort and silent: any failure is logged as an issue and never
        affects the chat reply. The LLM only proposes a typed steering note;
        the existing journey applier validates and upserts it.
        """
        if not bool(control_config.get("llm_conversation_memory_enabled", True)):
            return
        # Cheap prefilter: most chat is not a durable fact. Only spend an LLM call
        # when the message plausibly states something to remember. This keeps the
        # common chat turn down to fewer serial model calls (latency).
        if not _looks_like_memory_statement(message):
            return
        try:
            from wm.autoplay.memory_extract import build_memory_client, extract_memory_note

            identity = _chat_identity_facts(world_context or {}, player_guid=int(player_guid))
            client = build_memory_client(LmStudioClient, self._llm_settings(control_config), control_config=control_config)
            note = extract_memory_note(client=client, player_guid=int(player_guid), message=str(message), identity=identity)
            if not note:
                return
            self._persist_conversation_memory(settings=settings, player_guid=int(player_guid), note=note)
        except Exception as exc:
            self.store.add_issue({"reason": "conversation_memory_failed", "kind": "memory", "detail": str(exc)[:500]})

    def _persist_conversation_memory(self, *, settings: Settings, player_guid: int, note: dict[str, Any]) -> None:
        from wm.character.journey import CharacterJourneyStore, JOURNEY_PLAN_SCHEMA_VERSION
        from wm.character.memory import load_memory_entries
        from wm.db.mysql_cli import MysqlCliClient

        plan = {
            "schema_version": JOURNEY_PLAN_SCHEMA_VERSION,
            "player_guid": int(player_guid),
            "conversation_steering": [{
                "steering_key": note["steering_key"],
                "steering_kind": note["steering_kind"],
                "body": note["body"],
                "source": note.get("source", "conversation"),
            }],
        }
        client = MysqlCliClient()
        applier = CharacterJourneyStore(client=client, settings=settings)
        result = applier.apply_plan(plan=plan, mode="apply")
        persisted = False
        if result.ok:
            rows = load_memory_entries(client=client, settings=settings, player_guid=int(player_guid))
            persisted = any(
                str(row.get("SteeringKey") or "") == str(note["steering_key"])
                and str(row.get("Body") or "") == str(note["body"])
                and str(row.get("IsActive") or "").lower() in {"1", "true"}
                for row in rows
            )
        self.store.append_journal("conversation_memory", {
            "at": utc_now_iso(),
            "player_guid": int(player_guid),
            "steering_key": str(note["steering_key"]),
            "steering_kind": str(note["steering_kind"]),
            "ok": persisted,
            "error": getattr(result, "error", None)
            or ("not_active_after_upsert" if result.ok and not persisted else None),
        })
        if result.ok and not persisted:
            self.store.add_issue({
                "reason": "conversation_memory_not_persisted",
                "kind": "memory",
                "steering_key": str(note["steering_key"]),
            })

    def _dispatch_chat_parts(
        self,
        *,
        settings: Settings,
        player_guid: int,
        message: str,
        source_message: str,
    ) -> tuple[list[str], bool, list[dict[str, Any]]]:
        """Split message into <=220-char parts and send each as its own chat packet."""
        coordinator = self._control_coordinator(settings)
        parts = _split_chat_message(message)
        results: list[dict[str, Any]] = []
        overall_ok = bool(parts)
        for part in parts:
            proposal = _chat_action_proposal(player_guid=player_guid, message=part, source_message=source_message)
            dry = coordinator.execute(proposal=proposal, mode="dry-run", confirm_live_apply=False)
            if dry.status != "dry-run":
                results.append({"part": part, "stage": "dry_run", "dry_run": _result_to_dict(dry), "apply": None, "ok": False})
                return parts, False, results
            applied = coordinator.execute(proposal=proposal, mode="apply", confirm_live_apply=True)
            ok = applied.status == "applied"
            results.append({"part": part, "stage": "apply", "dry_run": _result_to_dict(dry), "apply": _result_to_dict(applied), "ok": ok})
            if not ok:
                overall_ok = False
        return parts, overall_ok, results

    def _speak(
        self,
        *,
        settings: Settings,
        player_guid: int,
        text: str,
        source_message: str,
    ) -> dict[str, Any]:
        parts, ok, results = self._dispatch_chat_parts(
            settings=settings, player_guid=player_guid, message=text, source_message=source_message,
        )
        if not parts:
            return {"ok": False, "error": "speak_empty"}
        if any(r.get("stage") == "dry_run" for r in results):
            return {"ok": False, "error": "speak_dry_run_failed"}
        return {"ok": ok, "parts": parts, "apply": results[-1]["apply"]}

    def _apply_compiled(
        self,
        *,
        settings: Settings,
        player_guid: int,
        compiled: Any,
        source_message: str,
    ) -> dict[str, Any]:
        from wm.autoplay.verification import verify_control_result
        from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID

        coordinator = self._control_coordinator(settings)
        applied = coordinator.execute(proposal=compiled.proposal, mode="apply", confirm_live_apply=True)
        meta = NATIVE_ACTION_KIND_BY_ID.get(compiled.verb)
        verification = verify_control_result(
            verb=compiled.verb,
            applied_result=applied,
            expected_effect=getattr(compiled.proposal, "expected_effect", None),
            strategy=getattr(meta, "verification_strategy", "native_request_done"),
        )
        record = {
            "at": utc_now_iso(),
            "player_guid": int(player_guid),
            "verb": compiled.verb,
            "risk": compiled.risk,
            "source_message": source_message,
            "apply": _result_to_dict(applied),
            "verification": verification,
        }
        self.store.append_journal("deed", record)
        ok = bool(verification.get("ok"))
        self._audit_intent(
            player_guid=player_guid,
            verb=compiled.verb,
            outcome="applied" if ok else "apply_failed",
            source_message=source_message,
            reason="" if ok else str(record),
            mode=compiled.mode,
            risk=compiled.risk,
            verification=verification,
        )
        counters_status = self.store.load_status()
        counters = dict(counters_status.get("counters") or {})
        counters["auto_applied"] = int(counters.get("auto_applied") or 0) + (1 if ok else 0)
        self.store.update_status(counters=counters, latest_verification=verification)
        if ok:
            msg = f"Done - {compiled.verb.replace('_', ' ')}."
        else:
            from wm.autoplay.intent import intent_failure_message
            msg = intent_failure_message(reason=str(record), verb=compiled.verb)
        self._speak(settings=settings, player_guid=player_guid, text=msg, source_message=source_message)
        if not ok:
            self.store.add_issue({"reason": "intent_apply_failed", "kind": "intent", "detail": record})
        return {"intent": "applied" if ok else "apply_failed", "verb": compiled.verb, "player_message": msg}

    def _apply_durable_native_intent(
        self, *, settings: Settings, player_guid: int, compiled: Any,
        source_event_key: str | None, source_message: str,
    ) -> dict[str, Any]:
        if not source_event_key:
            return {"intent": "unavailable", "verb": compiled.verb, "reason": "durable_origin_required"}
        from wm.autoplay.durable_native import DirectorLedger, run_durable_native_intent
        from wm.db.mysql_cli import MysqlCliClient
        from wm.sources.native_bridge.actions import NativeBridgeActionClient

        origin_key = f"wm_chat:{int(player_guid)}:{source_event_key}"
        native = NativeBridgeActionClient(client=MysqlCliClient(), settings=settings)
        try:
            result = run_durable_native_intent(
                ledger=DirectorLedger(settings=settings), origin_key=origin_key,
                player_guid=player_guid, verb=compiled.verb, proposal=compiled.proposal,
                apply=lambda: self._control_coordinator(settings).execute(
                    proposal=compiled.proposal, mode="apply", confirm_live_apply=True,
                ),
                lookup_native=lambda key: native.get_by_idempotency_key(idempotency_key=key),
            )
        except Exception as exc:
            self.store.add_issue({
                "reason": "durable_native_intent_unavailable", "kind": "intent",
                "detail": str(exc)[:500], "payload": {"origin_key": origin_key},
            })
            return {"intent": "unavailable", "verb": compiled.verb, "reason": "durable_store_unavailable"}
        state = result["state"]
        self._audit_intent(
            player_guid=player_guid, verb=compiled.verb, outcome=state,
            source_message=source_message, mode=compiled.mode, risk=compiled.risk,
            verification={"request_id": result["request_id"], "state": state},
        )
        return {"intent": "applied" if state == "verified" else state,
                "verb": compiled.verb, "request_id": result["request_id"]}

    def _apply_durable_director_intent(
        self, *, settings: Settings, player_guid: int, compiled: Any,
        source_event_key: str | None, source_message: str, dry_run: Any,
        source_event_at: str | None,
    ) -> dict[str, Any]:
        if not source_event_key or not source_event_at:
            return {"intent": "unavailable", "verb": compiled.verb, "reason": "durable_origin_required"}
        from wm.autoplay.director_work import DirectorWorkLedger, FrozenWork
        from wm.autoplay.policy import AutoplayPolicy

        status = self.store.load_status()
        runtime_config = status.get("config") or {}
        saved_policy = status.get("policy") or {}
        if (not status.get("running") or status.get("paused") or not saved_policy
                or not runtime_config.get("durable_director_enabled")
                or int(runtime_config.get("durable_director_player_guid") or 0) != player_guid):
            return {"intent": "unavailable", "verb": compiled.verb, "reason": "director_scope_or_policy_inactive"}
        policy = AutoplayPolicy(
            max_auto_risk=str(saved_policy.get("max_auto_risk") or "low"),
            enabled_lanes=set(saved_policy.get("enabled_lanes") or []),
            lane_budgets=dict(saved_policy.get("lane_budgets") or {}),
            max_source_event_age_seconds=int(saved_policy.get("max_source_event_age_seconds") or 3600),
            require_rollback_for_lanes=set(saved_policy.get("require_rollback_for_lanes") or []),
        ).decide(
            schema_version="control.proposal.v1", lane="action", risk=compiled.risk,
            readiness_ok=bool(self._readiness(settings).get("ok")), lm_ok=True,
            session_ok=True, source_event_at=source_event_at,
            dry_run_ok=dry_run.status == "dry-run", rollback_available=True,
            idempotency_seen=compiled.proposal.idempotency_key in self.store.load_idempotency_keys(),
            lane_applied_count=_applied_lane_counts(status).get("action", 0),
        )
        if not policy.ok:
            return {"intent": "unavailable", "verb": compiled.verb,
                    "reason": "director_policy_blocked", "blockers": policy.blockers}

        ledger = DirectorWorkLedger(settings=settings)
        origin = f"wm_chat:{player_guid}:{source_event_key}"
        artifact = FrozenWork.from_runtime({"kind": "control", "proposals": [compiled.proposal]})
        work = None
        try:
            work = ledger.prepare(
                origin_key=origin, player_guid=player_guid, lane="action", artifact=artifact,
                preview=dry_run.to_dict(),
                evidence={"source_event_key": source_event_key, "message": source_message[:1000]},
            )
            if work.state == "received":
                work = ledger.authorize(
                    work, policy={**policy.to_dict(), "verb": compiled.verb,
                                  "mode": compiled.mode, "scope": player_guid},
                    mode="automatic", expires_seconds=120,
                )
            if work.state == "authorized":
                current = self.store.load_status()
                current_config = current.get("config") or {}
                if (not current.get("running") or current.get("paused")
                        or current.get("policy") != saved_policy
                        or not current_config.get("durable_director_enabled")
                        or int(current_config.get("durable_director_player_guid") or 0) != player_guid
                        or not self._readiness(settings).get("ok")):
                    raise RuntimeError("director_policy_or_scope_changed_before_claim")
                work = ledger.claim(work)
                try:
                    results = _execute_runtime_work(
                        runtime=work.artifact.thaw(), coordinator=self._control_coordinator(settings),
                        mode="apply",
                    )
                    work = ledger.record_result(work, results=results)
                except BaseException:
                    ledger.mark_uncertain(work, reason="executor_outcome_unknown")
                    raise
        except Exception as exc:
            self.store.add_issue({"reason": "director_intent_unavailable", "kind": "intent",
                                  "detail": str(exc)[:500], "payload": {"origin_key": origin}})
            return {"intent": "unavailable", "verb": compiled.verb,
                    "reason": "director_effect_outcome_unknown" if work and work.state == "dispatching" else "director_store_unavailable"}
        return {"intent": work.state, "verb": compiled.verb,
                "request_id": work.request_id, "proof": "pending" if work.state == "applied" else work.state}

    def _apply_pending(
        self,
        *,
        settings: Settings,
        player_guid: int,
        pending: dict[str, Any],
        source_message: str,
    ) -> dict[str, Any]:
        from wm.autoplay.intent import CompiledIntent
        from wm.control.models import ControlProposal

        if pending.get("kind") == "scene":
            self.store.clear_pending_intent(player_guid, reason="player_confirmed")
            return self._run_scene(
                settings=settings, player_guid=player_guid,
                scene_name=str(pending.get("scene_name") or "scene"),
                steps=pending.get("steps") if isinstance(pending.get("steps"), list) else [],
                source_message=source_message,
            )

        proposal = ControlProposal.model_validate(pending["proposal"])
        compiled = CompiledIntent(
            proposal=proposal,
            verb=pending.get("verb", "action"),
            mode="confirm",
            risk=pending.get("risk", "medium"),
        )
        result = self._apply_compiled(settings=settings, player_guid=player_guid,
                                      compiled=compiled, source_message=source_message)
        if result.get("intent") == "applied":
            self.store.clear_pending_intent(player_guid, reason="player_confirmed")
        return result

    def _handle_scene_request(
        self,
        *,
        settings: Settings,
        control_config: dict[str, Any],
        player_guid: int,
        message: str,
        world_context: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Phase 5: compose an LLM scene from a chat request and park it for confirm.

        Returns a pending record when a valid multi-step scene was composed, else
        None (so the normal single-action path handles the message). Best-effort.
        """
        if not bool(control_config.get("llm_scene_director_enabled", True)):
            return None
        try:
            from wm.autoplay.intent_extract import build_intent_client
            from wm.autoplay.scene_compose import extract_scene_request
            from wm.targets.name_resolver import get_default_creature_name_resolver

            identity = _chat_identity_facts(world_context or {}, player_guid=int(player_guid))
            client = build_intent_client(LmStudioClient, self._llm_settings(control_config), control_config=control_config)
            scene = extract_scene_request(
                client=client, player_guid=int(player_guid), message=str(message),
                identity=identity, resolver=get_default_creature_name_resolver(),
            )
        except Exception as exc:
            self.store.add_issue({"reason": "scene_compose_failed", "kind": "scene", "detail": str(exc)[:500]})
            return None
        if scene is None:
            return None
        self.store.set_pending_intent(player_guid, {
            "kind": "scene",
            "scene_name": scene.scene_name,
            "steps": scene.steps,
            "risk": "medium",
            "summary": f"scene {scene.scene_name} ({len(scene.steps)} steps)",
        }, ttl_seconds=120)
        self._speak(settings=settings, player_guid=player_guid,
                    text=f"I can stage {scene.scene_name} ({len(scene.steps)} steps) - say yes to begin.",
                    source_message=message)
        return {"scene": "pending", "scene_name": scene.scene_name, "steps": len(scene.steps)}

    def _run_scene(
        self,
        *,
        settings: Settings,
        player_guid: int,
        scene_name: str,
        steps: list[dict[str, Any]],
        source_message: str,
    ) -> dict[str, Any]:
        from wm.autoplay.verification import verify_control_result
        from wm.control.models import ControlProposal
        from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID

        if not steps:
            return {"scene": "empty", "scene_name": scene_name}
        coordinator = self._control_coordinator(settings)
        run_key = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        step_results: list[dict[str, Any]] = []
        ok_all = True
        for index, step in enumerate(steps):
            verb = str(step.get("native_action_kind") or "")
            payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
            # Use each verb's own default risk (creature_say is low, creature_spawn
            # is medium, etc.) so per-action policy gates accept the step.
            kind = NATIVE_ACTION_KIND_BY_ID.get(verb)
            step_risk = kind.default_risk if kind is not None else "low"
            proposal = ControlProposal.model_validate({
                "schema_version": "control.proposal.v1",
                "source_event": None,
                "player": {"guid": int(player_guid)},
                "selected_recipe": "manual_admin_action",
                "action": {
                    "kind": "native_bridge_action",
                    "payload": {
                        "native_action_kind": verb,
                        "payload": payload,
                        "created_by": f"wm.autoplay.scene:{scene_name}",
                        "risk_level": step_risk,
                        "expires_seconds": 120,
                    },
                },
                "rationale": f"Scene {scene_name} step {index}: {verb}",
                "risk": {"level": step_risk, "irreversible": False, "notes": []},
                "idempotency_key": f"autoplay:scene:{int(player_guid)}:{run_key}:{index}",
                "author": {
                    "kind": "manual_admin", "name": "wm.autoplay.scene",
                    "manual_reason": f"operator-authorized scene {scene_name}",
                },
                "metadata": {"lane": "scene", "scene_name": scene_name, "scene_step": index},
            })
            applied = coordinator.execute(proposal=proposal, mode="apply", confirm_live_apply=True)
            status_value = getattr(applied, "status", "error")
            verification = verify_control_result(
                verb=verb,
                applied_result=applied,
                expected_effect=str(step.get("expected_effect") or ""),
                strategy=getattr(kind, "verification_strategy", "native_request_done"),
            )
            step_results.append({"index": index, "verb": verb, "status": status_value, "verification": verification})
            if not verification.get("ok"):
                ok_all = False
                break
        record = {
            "at": utc_now_iso(),
            "player_guid": int(player_guid),
            "scene_name": scene_name,
            "steps_total": len(steps),
            "steps_executed": len(step_results),
            "cleanup_status": _scene_cleanup_status(steps),
            "ok": ok_all,
            "step_results": step_results,
        }
        self.store.append_journal("scene_run", record)
        self.store.update_status(latest_verification={
            "schema_version": "wm.autoplay.verification.v1",
            "at": utc_now_iso(),
            "verb": "scene",
            "strategy": "scene_steps",
            "status": "verified" if ok_all else "failed",
            "ok": ok_all,
            "step_count": len(step_results),
        })
        self._speak(settings=settings, player_guid=player_guid,
                    text=("The scene plays out as willed." if ok_all else "The scene falters partway through."),
                    source_message=source_message)
        return {"scene": "applied" if ok_all else "partial", "scene_name": scene_name,
                "steps_executed": len(step_results), "steps_total": len(steps)}

    def approve_pending(self, *, player_guid: int) -> dict[str, Any]:
        pending = self.store.load_pending_intent(int(player_guid))
        if not pending:
            return {"ok": False, "error": "no_pending_intent"}
        settings = Settings.from_env()
        result = self._apply_pending(settings=settings, player_guid=int(player_guid),
                                     pending=pending, source_message="(panel approval)")
        return {"ok": result.get("intent") == "applied", "result": result}

    def reject_pending(self, *, player_guid: int, reason: str = "panel_rejected") -> dict[str, Any]:
        self.store.clear_pending_intent(int(player_guid), reason=reason)
        return {"ok": True, "player_guid": int(player_guid)}

    def _drive_llm_generation(
        self,
        *,
        control_config: dict[str, Any],
        settings: Settings,
        readiness: dict[str, Any],
        session: dict[str, Any] | None,
        llm: dict[str, Any],
        status: dict[str, Any],
        force_lane: str | None = None,
        ignore_cooldown: bool = False,
    ) -> list[dict[str, Any]]:
        lanes = _normalize_lanes(control_config.get("llm_lanes"))
        chat_enabled = force_lane == "chat" or bool(control_config.get("llm_chat_enabled", True)) or "chat" in lanes
        ready_for_llm = bool(readiness.get("ok")) and bool(llm.get("ok"))
        if not ready_for_llm and not chat_enabled:
            return []
        if not session and not chat_enabled:
            return []
        if session and session.get("character_guid") in (None, "") and not chat_enabled:
            return []
        try:
            event_player_guid = None if chat_enabled else int((session or {})["character_guid"])
            events = self._recent_events(settings=settings, player_guid=event_player_guid)
        except Exception as exc:
            self.store.add_issue({
                "reason": "event_scan_failed",
                "kind": "llm",
                "detail": str(exc)[:1000],
            })
            return []
        seen = self.store.load_seen_event_keys()
        chat_results: list[dict[str, Any]] = []
        max_events = max(int(control_config.get("llm_events_per_tick") or 1), 1)
        for event in events:
            event_payload = event.to_dict() if hasattr(event, "to_dict") else dict(event)
            source_key = str(event_payload.get("source_event_key") or "")
            if not source_key or source_key in seen:
                continue
            if str(event_payload.get("event_type") or "") != "wm_chat":
                continue
            if force_lane not in (None, "chat"):
                continue
            metadata = event_payload.get("metadata") if isinstance(event_payload.get("metadata"), dict) else {}
            message = str(event_payload.get("event_value") or metadata.get("message") or "")
            note_command = message.strip().partition(" ")[0].casefold() in {"/note", "/note!", "/notes"}
            if not ready_for_llm and not _is_forget_context_command(message) and not note_command:
                continue
            result = self._reply_to_chat_event(
                control_config=control_config,
                settings=settings,
                session=session,
                event_payload=event_payload,
            )
            chat_results.append(result)
            if not result.get("retryable"):
                self.store.mark_event_seen(source_key)
            if len(chat_results) >= max_events:
                break
        if chat_results:
            return chat_results
        if not ready_for_llm:
            return []
        if not ignore_cooldown and _cooldown_active(status.get("latest_proposal"), seconds=int(control_config.get("llm_cooldown_seconds") or 60)):
            return []
        opportunities: list[dict[str, Any]] = []
        if not session or session.get("character_guid") in (None, ""):
            return []
        session_guid = int(session["character_guid"])
        if force_lane in (None, "quest") and "quest" in lanes:
            activity_result = self._drive_activity_opportunity(
                control_config=control_config, settings=settings, readiness=readiness,
                session=session, llm=llm,
            )
            if activity_result is not None:
                return [activity_result]
        for event in events:
            source_key = str(getattr(event, "source_event_key", "") or "")
            if not source_key or source_key in seen:
                continue
            if getattr(event, "player_guid", None) not in (None, session_guid):
                continue
            if control_config.get("initiative_preset") == "on_demand" and getattr(event, "event_type", "") not in {"quest_complete", "quest_completed", "quest_rewarded"}:
                continue
            if (control_config.get("durable_director_enabled")
                    and int(control_config.get("durable_director_player_guid") or 0) == int(session.get("character_guid") or 0)
                    and getattr(event, "event_type", "") in {"kill", "loot_item"}):
                # Activity summaries own unsolicited gathering opportunities in the selected director scope.
                continue
            opportunity = _opportunity_from_event(
                event=event,
                lanes=lanes,
                max_event_age_seconds=int(control_config.get("llm_event_age_seconds") or 300),
                force_lane=force_lane,
            )
            if opportunity is not None:
                opportunities.append(opportunity)
            if len(opportunities) >= max_events:
                break

        results: list[dict[str, Any]] = []
        for opportunity in opportunities:
            result = self._generate_for_opportunity(
                    control_config=control_config,
                    settings=settings,
                    readiness=readiness,
                    session=session,
                    llm=llm,
                    opportunity=opportunity,
                )
            results.append(result)
            source_key = str((opportunity.get("source_event") or {}).get("source_event_key") or "")
            if source_key and not result.get("retryable"):
                self.store.mark_event_seen(source_key)
        return results

    def _drive_activity_opportunity(
        self, *, control_config: dict[str, Any], settings: Settings,
        readiness: dict[str, Any], session: dict[str, Any], llm: dict[str, Any],
    ) -> dict[str, Any] | None:
        from wm.autoplay.activities import _time, read_activity_context
        from wm.autoplay.director_intake import DirectorIntakeLedger
        from wm.autoplay.director_work import DirectorWorkLedger

        guid = int(session["character_guid"])
        preset = control_config.get("initiative_preset", "moderate")
        if (preset == "on_demand" or not control_config.get("activity_proposals_enabled", True)
                or not control_config.get("durable_director_enabled")
                or guid != int(control_config.get("durable_director_player_guid") or 0)):
            return None
        scan_at = time.monotonic()
        if scan_at - self._activity_scan_at.get(guid, float("-inf")) < 15:
            return None
        self._activity_scan_at[guid] = scan_at
        try:
            activity = read_activity_context(player_guid=guid, settings=settings)
            if not activity["inventory_fresh"]:
                return None
            threshold, cooldown = (2, 300) if preset == "active" else (3, 900)
            now = datetime.now(timezone.utc)
            episode = next((row for row in activity["episodes"] if row["source_count"] >= threshold
                            and _time(row["last_observed_at"]) is not None
                            and (now - _time(row["last_observed_at"])).total_seconds() <= 120), None)
            if episode is None:
                return None
            work_rows = DirectorWorkLedger(settings=settings).list_recent(player_guid=guid, limit=30)
            if any(row["state"] in {"received", "authorized", "dispatching", "uncertain"} for row in work_rows):
                return None
            source_key = f"activity:{guid}:{episode['episode_key']}"
            opportunity_id = f"activity-{guid}-{episode['episode_key']}"
            draft_id = f"autoplay-{opportunity_id}"
            if any(row["origin_key"] == f"autoplay:quest:{draft_id}" for row in work_rows):
                return None
            if any(row.get("draft_id") == draft_id for row in self.store.load_status().get("proposal_queue", [])):
                return None
            intakes = DirectorIntakeLedger(settings=settings).list_recent(player_guid=guid, limit=30)
            for row in intakes:
                if not (row["evidence"].get("initiative") or {}).get("proactive"):
                    continue
                if row["origin_key"] == f"director:decision:{source_key}":
                    if (row.get("decision") or {}).get("outcome") != "propose_content":
                        return None
                    continue
                stamp = _time(row.get("decided_at") or row.get("created_at"))
                if stamp and (now - stamp).total_seconds() < cooldown:
                    return None
            world = self._chat_world_context(settings=settings, player_guid=guid, message="", source_event={})
            world["activities"] = activity
            if (world.get("live_location") or {}).get("in_combat"):
                return None
            active_quests = {int(row["quest"]) for row in (world.get("database") or {}).get("active_quests", [])}
            for row in work_rows:
                actions = ((row.get("artifact") or {}).get("plan") or {}).get("actions", [])
                if any(action.get("kind") == "quest_publish"
                       and (action.get("payload", {}).get("objective") or {}).get("kind") == "deliver"
                       and int(action.get("payload", {}).get("quest_id") or 0) in active_quests
                       for action in actions):
                    return None
            if any(row["lane"] == "quest" and row["state"] == "applied"
                   and (now - _time(row["created_at"])).total_seconds() < cooldown for row in work_rows):
                return None
            decision = self._decide_director_chat(
                control_config=control_config, player_guid=guid, message="",
                world_context=world, source_key=source_key, source_event_at=episode["last_observed_at"],
                proactive=True,
            )
            if decision.outcome != "propose_content" or decision.capability != "material_delivery":
                return {"ok": True, "decision": decision.outcome, "activity": episode, "action": "none"}
            opportunity = {
                "opportunity_id": opportunity_id, "stable_key": episode["episode_key"],
                "source_event_key": source_key, "source_event_at": episode["last_observed_at"],
                "source_event": {"event_type": "gathering_activity", "player_guid": guid,
                                 "source_event_key": source_key, "occurred_at": episode["last_observed_at"],
                                 "subject_type": "item", "subject_entry": episode["item_entry"]},
                "lane": "quest", "schema_version": "wm.quest.release.material_delivery.v1",
                "player_guid": guid, "activity": episode, "risk": "low",
            }
            return self._generate_for_opportunity(
                control_config=control_config, settings=settings, readiness=readiness,
                session=session, llm=llm, opportunity=opportunity,
            )
        except Exception as exc:
            self.store.add_issue({"reason": "activity_opportunity_unavailable", "kind": "activity", "detail": str(exc)[:500]})
            return None

    def _generate_for_opportunity(
        self,
        *,
        control_config: dict[str, Any],
        settings: Settings,
        readiness: dict[str, Any],
        session: dict[str, Any] | None,
        llm: dict[str, Any],
        opportunity: dict[str, Any],
    ) -> dict[str, Any]:
        del readiness, llm
        self.store.add_opportunity(opportunity)
        player_guid = int((session or {}).get("character_guid") or opportunity.get("player_guid") or 0)
        schema_version = str(opportunity["schema_version"])
        adapter = self._llm_adapter(control_config)
        session_pack = build_session_context_pack(player_guid=player_guid, settings=settings)
        context_pack = _compact_autoplay_context(
            session_pack,
            opportunity=opportunity,
            player_guid=player_guid,
        )
        context_pack["author_notes"] = self.panel_state.author_notes.context(player_guid)
        context_notes = context_pack.get("context_notes") or []
        memory_unavailable = any(str(note).startswith("memory_context:") for note in context_notes)
        if context_pack.get("context_status") == "UNKNOWN" or not context_pack.get("character_state") or memory_unavailable:
            return {"ok": False, "retryable": True, "lane": opportunity.get("lane"), "reason": "character_context_unavailable"}
        facts = _deterministic_facts(opportunity=opportunity, player_guid=player_guid, control_config=control_config)
        quest_candidates = None
        if (opportunity.get("lane") == "quest" and (opportunity.get("player_request") or opportunity.get("activity"))
                and control_config.get("durable_director_enabled")
                and player_guid == int(control_config.get("durable_director_player_guid") or 0)):
            from wm.autoplay.quest_feasibility import discover_quest_candidates, discover_delivery_candidates

            try:
                discover = discover_delivery_candidates if schema_version == "wm.quest.release.material_delivery.v1" else discover_quest_candidates
                quest_candidates = discover(player_guid=player_guid, settings=settings)
            except Exception as exc:
                self.store.add_issue({"reason": "quest_candidate_discovery_failed", "kind": "quest", "detail": str(exc)[:500]})
                return {"ok": False, "retryable": True, "lane": "quest", "reason": "quest_candidate_discovery_failed"}
            if not quest_candidates["candidates"]:
                self.store.add_issue({"reason": "no_feasible_quest_candidates", "kind": "quest", "payload": quest_candidates})
                return {"ok": False, "retryable": True, "lane": "quest", "reason": "no_feasible_quest_candidates"}
            facts["delivery_candidates" if schema_version == "wm.quest.release.material_delivery.v1" else "quest_candidates"] = quest_candidates["candidates"]
            facts["quest_player_level"] = quest_candidates["player"]["level"]
            if opportunity.get("activity"):
                context_pack["activity"] = {key: value for key, value in opportunity["activity"].items()
                                            if key not in {"event_keys", "kill_targets"}}
        instruction = _instruction_for_opportunity(opportunity) + " " + context_pack["author_notes"]["rules"]
        result = adapter.generate(
            schema_version=schema_version,
            instruction=instruction,
            context_pack=context_pack,
            candidate_pack={
                "opportunity": _compact_opportunity_for_llm(opportunity),
                "policy": self.policy.to_dict(),
                "wm_tools": autoplay_tool_manifest(),
                **({"quest_candidates": {key: value for key, value in quest_candidates.items() if key != "activity"}}
                   if quest_candidates else {}),
            },
            deterministic_facts=facts,
        )
        draft_id = f"autoplay-{opportunity['opportunity_id']}"
        record = {
            "draft_id": draft_id,
            "ok": result.ok,
            "origin": "autoplay_llm",
            "state": "VALIDATED" if result.ok else "PARKED",
            "lane": opportunity.get("lane"),
            "schema_version": schema_version,
            "player_guid": player_guid,
            "created_at": utc_now_iso(),
            "settings": self._llm_settings(control_config).to_safe_dict(),
            "opportunity": opportunity,
            "instruction": instruction,
            "parsed_json": result.draft,
            "issues": result.issues,
            "request": _compact_request(result.request),
            "raw_content": result.raw_content,
            "author_notes": context_pack["author_notes"],
            "memory_revision": _memory_revision(
                active=session_pack.get("memory") or [],
                evidence=session_pack.get("memory_source_evidence") or [],
                excluded=session_pack.get("memory_exclusions") or [],
            ),
        }
        if result.ok:
            saved = self.store.add_draft(record)
            self.panel_state.save_draft({**record, "validation": {"ok": True, "issues": []}})
            return {"ok": True, "draft_id": saved["draft_id"], "lane": opportunity.get("lane"), "schema_version": schema_version}
        retryable = any(str(item.get("path") or "").startswith("llm") for item in result.issues)
        issue = self.store.add_issue({
            "reason": "llm_draft_invalid",
            "kind": str(opportunity.get("lane") or "llm"),
            "detail": "; ".join(str(item.get("message")) for item in result.issues[:3]) if result.issues else "unknown",
            "payload": record,
        })
        return {"ok": False, "retryable": retryable, "draft_id": draft_id, "lane": opportunity.get("lane"), "issue": _compact_store_result(issue)}

    def _drive_ambient_narration(
        self,
        *,
        control_config: dict[str, Any],
        settings: Settings,
        readiness: dict[str, Any],
        session: dict[str, Any] | None,
        llm: dict[str, Any],
        status: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Phase 2: WM speaks one short ambient line on a notable, fresh event.

        Returns a record when a notable cue was found and an attempt was made
        (so the caller can set the cooldown anchor), or None when disabled,
        not ready, on cooldown, or nothing notable happened.
        """
        if not bool(control_config.get("llm_ambient_narration_enabled", True)) or control_config.get("initiative_preset") == "on_demand":
            return None
        if not (bool(readiness.get("ok")) and bool(llm.get("ok"))):
            return None
        if not session or session.get("character_guid") in (None, ""):
            return None
        cooldown = int(control_config.get("llm_ambient_cooldown_seconds") or 150)
        guid = int(session["character_guid"])
        try:
            events = self._recent_events(settings=settings, player_guid=guid)
        except Exception as exc:
            self.store.add_issue({"reason": "ambient_event_scan_failed", "kind": "ambient", "detail": str(exc)[:500]})
            return None
        seen = self.store.load_seen_event_keys()
        max_age = int(control_config.get("llm_event_age_seconds") or 300)
        # Gather all fresh, unseen notable cues (events arrive newest-first).
        candidates: list[Any] = []
        for event in events:
            payload = event.to_dict() if hasattr(event, "to_dict") else dict(event)
            if payload.get("player_guid") not in (None, guid):
                continue
            key = str(payload.get("source_event_key") or "")
            if not key or key in seen:
                continue
            occurred = _parse_time(str(payload.get("occurred_at") or ""))
            if occurred is not None and (datetime.now(timezone.utc) - occurred).total_seconds() > max_age:
                continue
            candidate = classify_ambient_event(payload)
            if candidate is not None:
                candidates.append(candidate)
        if not candidates:
            return None
        # Prefer a high-priority moment (death/level-up); it bypasses the cooldown
        # so it is never starved by routine zone-hopping. Routine cues stay throttled.
        high = [c for c in candidates if c.kind in HIGH_PRIORITY_AMBIENT_KINDS]
        if high:
            cue = high[0]
        else:
            if _cooldown_active(status.get("latest_ambient"), seconds=cooldown):
                cue = candidates[0]
                # A cooldown decision is proof-relevant and the eligible event
                # must not become delayed narration after the window expires.
                self.store.mark_event_seen(cue.source_event_key)
                self.store.append_journal(
                    "ambient_suppressed",
                    {
                        "player_guid": guid,
                        "reason": "cooldown_active",
                        "cooldown_seconds": cooldown,
                        "kind": cue.kind,
                        "descriptor": cue.descriptor,
                        "source_event_key": cue.source_event_key,
                        "ambient_anchor_at": (status.get("latest_ambient") or {}).get("at"),
                    },
                )
                return None
            cue = candidates[0]
        # Claim the moment before generating so a slow/failed call cannot re-fire it.
        self.store.mark_event_seen(cue.source_event_key)
        line = self._narrate_ambient_cue(
            control_config=control_config, settings=settings, player_guid=guid, cue=cue,
        )
        record = {
            "at": utc_now_iso(),
            "player_guid": guid,
            "kind": cue.kind,
            "descriptor": cue.descriptor,
            "source_event_key": cue.source_event_key,
            "line": line.get("message"),
            "ok": bool(line.get("ok")),
        }
        self.store.append_journal("ambient_narration", record)
        return record

    def _narrate_ambient_cue(
        self,
        *,
        control_config: dict[str, Any],
        settings: Settings,
        player_guid: int,
        cue: Any,
    ) -> dict[str, Any]:
        llm_settings = self._llm_settings(control_config)
        try:
            world = build_chat_world_context(settings=settings, player_guid=int(player_guid), message="")
        except Exception:
            world = {"speaker": {"guid": int(player_guid)}}
        identity = _chat_identity_facts(world, player_guid=int(player_guid))
        messages = build_ambient_messages(cue, identity)
        from wm.author_notes import NOTE_RULES
        messages[0]["content"] += " " + NOTE_RULES
        messages.append({"role": "user", "content": "author_notes: " + json.dumps(
            self.panel_state.author_notes.context(int(player_guid)), ensure_ascii=False)})
        client = LmStudioClient(replace(llm_settings, schema_mode="text", max_tokens=_chat_max_tokens(llm_settings)))
        try:
            result = client.generate_text(messages=messages)
        except Exception as exc:
            self.store.add_issue({"reason": "ambient_narration_failed", "kind": "ambient", "detail": str(exc)[:500]})
            return {"ok": False, "error": str(exc)[:200], "message": None}
        content = str(result.get("content") or "").strip()
        line = _guard_chat_reply(_sanitize_chat_reply(content))
        if not line:
            return {"ok": False, "error": "empty", "message": None}
        spoken = self._speak(settings=settings, player_guid=int(player_guid), text=line, source_message=f"ambient:{cue.kind}")
        return {"ok": bool(spoken.get("ok")), "message": line, "speak": spoken}

    def _recent_events(self, *, settings: Settings, player_guid: int | None = None) -> list[Any]:
        from wm.db.mysql_cli import MysqlCliClient
        from wm.events.store import EventStore
        from wm.sources.native_bridge.adapter import NativeBridgeAdapter

        client = MysqlCliClient()
        store = EventStore(client=client, settings=settings)
        if player_guid is None:
            _ingest_recent_native_bridge_chat(client=client, settings=settings, store=store)
        else:
            adapter = NativeBridgeAdapter(
                client=client,
                settings=settings,
                store=store,
                batch_size=100,
                player_guid_filter=int(player_guid),
            )
            try:
                events = adapter.poll()
                if events:
                    store.record(events)
                if adapter.last_cursor_value is not None:
                    store.set_cursor(adapter_name=adapter.name, cursor_key=adapter.cursor_key, cursor_value=adapter.last_cursor_value)
            except Exception:
                # The external watcher is still allowed to feed wm_event_log. If the
                # direct native poll fails, keep scanning the normalized event store.
                pass
        return store.list_recent_events(
            event_class="observed",
            player_guid=(int(player_guid) if player_guid is not None else None),
            limit=25,
            newest_first=True,
        )

    def _load_event(self, *, settings: Settings, event_id: int | None, source_event_key: str | None) -> Any | None:
        from wm.db.mysql_cli import MysqlCliClient
        from wm.events.store import EventStore

        store = EventStore(client=MysqlCliClient(), settings=settings)
        if event_id is not None:
            return store.get_event(event_id=int(event_id))
        if source_event_key:
            for event in store.list_recent_events(limit=100, newest_first=True):
                if str(event.source_event_key) == str(source_event_key):
                    return event
        return None

    def _control_coordinator(self, settings: Settings) -> Any:
        from wm.control._cli import build_live_coordinator

        return build_live_coordinator(settings)

    def _drive_validated_drafts(
        self,
        *,
        control_config: dict[str, Any],
        settings: Settings,
        readiness: dict[str, Any],
        session: dict[str, Any] | None,
        llm: dict[str, Any],
        safe_window: SafeWindow,
        status: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not readiness.get("ok"):
            return []
        if not llm.get("ok"):
            return []
        if not session or session.get("character_guid") in (None, ""):
            return []
        pending = [
            item
            for item in status.get("proposal_queue") or []
            if isinstance(item, dict)
            and str(item.get("state") or "") == "VALIDATED"
            and str(item.get("lane") or "") in {"quest", "item", "spell", "ability", "scene", "action"}
        ]
        if not pending:
            return []

        coordinator = self._control_coordinator(settings)
        lane_counts = _applied_lane_counts(status)
        seen_idempotency = self.store.load_idempotency_keys()
        results: list[dict[str, Any]] = []
        for record in pending[:1]:
            draft_id = str(record.get("draft_id") or "")
            lane = str(record.get("lane") or "")
            schema_version = str(record.get("schema_version") or "")
            payload = record.get("parsed_json") if isinstance(record.get("parsed_json"), dict) else {}
            director_scope = bool(control_config.get("durable_director_enabled")) and lane in {"quest", "action"}
            feasibility: dict[str, Any] | None = None
            if record.get("origin") == "autoplay_llm":
                memory_blocker = self._draft_memory_blocker(
                    record=record, settings=settings, player_guid=int(session["character_guid"]),
                )
                if memory_blocker:
                    issue = self.store.add_issue({
                        "reason": memory_blocker, "kind": lane, "payload": _compact_draft_record(record),
                    })
                    self.store.update_draft(draft_id, {
                        "state": "PARKED",
                        "issues": [*_as_list(record.get("issues")), _compact_store_result(issue)],
                    })
                    results.append({"draft_id": draft_id, "lane": lane, "status": "parked", "issue": _compact_store_result(issue)})
                    continue
            try:
                runtime = _runtime_work_from_draft(record=record, settings=settings)
                if director_scope and lane == "quest":
                    from wm.autoplay.quest_feasibility import assess_quest_plan

                    feasibility = assess_quest_plan(plan=runtime["plan"], settings=settings)
            except Exception as exc:
                issue = self.store.add_issue({
                    "reason": "runtime_compile_failed",
                    "kind": lane,
                    "detail": str(exc)[:1000],
                    "payload": _compact_draft_record(record),
                })
                update = {
                    "state": "PARKED",
                    "policy": {"status": "blocked", "blockers": ["runtime_compile_failed"]},
                    "issues": [*_as_list(record.get("issues")), _compact_store_result(issue)],
                }
                if draft_id:
                    self.store.update_draft(draft_id, update)
                results.append({"draft_id": draft_id, "lane": lane, "status": "parked", "issue": _compact_store_result(issue)})
                continue

            if runtime.get("kind") == "maintenance":
                maintenance = self.store.add_maintenance({
                    "reason": str(runtime.get("reason") or "maintenance_required"),
                    "kind": lane,
                    "payload": {"draft_id": draft_id, "lane": lane, "schema_version": schema_version},
                })
                self.store.update_draft(draft_id, {"state": "MAINTENANCE_PENDING"})
                results.append({
                    "draft_id": draft_id,
                    "lane": lane,
                    "status": "maintenance_pending",
                    "maintenance": _compact_store_result(maintenance),
                })
                continue

            dry_run_results = _execute_runtime_work(runtime=runtime, coordinator=coordinator, mode="dry-run")
            dry_run_payload = {
                "at": utc_now_iso(),
                "draft_id": draft_id,
                "lane": lane,
                "status": "complete" if _runtime_results_ok(dry_run_results, expected="dry-run") else "failed",
                "steps": [_result_to_dict(item) for item in dry_run_results],
            }
            if draft_id:
                self.store.update_draft(draft_id, {"latest_dry_run": dry_run_payload})

            idempotency_keys = _runtime_idempotency_keys(runtime)
            decision = self.policy.decide(
                schema_version=schema_version,
                payload=payload,
                lane=lane,
                risk=_risk_from_payload(payload),
                readiness_ok=bool(readiness.get("ok")),
                lm_ok=bool(llm.get("ok")),
                session_ok=True,
                source_event_at=_draft_source_event_at(record),
                dry_run_ok=dry_run_payload["status"] == "complete",
                rollback_available=_runtime_rollback_available(lane),
                idempotency_seen=any(key in seen_idempotency for key in idempotency_keys),
                lane_applied_count=int(lane_counts.get(lane, 0)),
                safe_window=safe_window,
            )
            decision_payload = decision.to_dict()
            base_result = {
                "draft_id": draft_id,
                "lane": lane,
                "schema_version": schema_version,
                "dry_run": dry_run_payload,
                "policy": decision_payload,
            }
            if dry_run_payload["status"] != "complete":
                issue = self.store.add_issue({"reason": "dry_run_failed", "kind": lane, "payload": dict(base_result)})
                self.store.update_draft(draft_id, {
                    "state": "PARKED",
                    "policy": decision_payload,
                    "issues": [*_as_list(record.get("issues")), _compact_store_result(issue)],
                })
                results.append({**base_result, "status": "parked", "issue": _compact_store_result(issue)})
                continue
            if decision.status == "maintenance_pending":
                maintenance = self.store.add_maintenance({
                    "reason": ",".join(decision.maintenance_reasons),
                    "kind": lane,
                    "payload": dict(base_result),
                })
                self.store.update_draft(draft_id, {"state": "MAINTENANCE_PENDING", "policy": decision_payload})
                results.append({**base_result, "status": "maintenance_pending", "maintenance": _compact_store_result(maintenance)})
                continue
            operator_risk_only = (
                director_scope and bool(decision.blockers) and not decision.maintenance_reasons
                and all(blocker.startswith("risk_exceeds_policy:") for blocker in decision.blockers)
            )
            if operator_risk_only:
                try:
                    from wm.autoplay.director_work import DirectorWorkLedger, FrozenWork

                    selected_guid = int(control_config.get("durable_director_player_guid") or 0)
                    runtime_guid = (int(runtime["plan"].player_guid) if runtime["kind"] == "plan"
                                    else int(runtime["proposals"][0].player.guid))
                    if selected_guid <= 0 or selected_guid != int(session["character_guid"]) or runtime_guid != selected_guid:
                        raise ValueError("director_scope_mismatch")
                    artifact = FrozenWork.from_runtime(runtime)
                    work = DirectorWorkLedger(settings=settings).prepare(
                        origin_key=f"autoplay:{lane}:{draft_id}", player_guid=selected_guid,
                        lane=lane, artifact=artifact, preview=dry_run_payload,
                        evidence={"draft_id": draft_id, "schema_version": schema_version,
                                  "source_event_at": _draft_source_event_at(record),
                                  "memory_revision": record.get("memory_revision"),
                                  "quest_feasibility": feasibility,
                                  "risk": _risk_from_payload(payload)},
                    )
                    if work.state != "received":
                        raise RuntimeError(f"director_work_already_{work.state}")
                    self.store.update_draft(draft_id, {"state": "AWAITING_APPROVAL", "policy": decision_payload,
                                                       "director_request_id": work.request_id,
                                                       "artifact_hash": artifact.artifact_hash})
                    results.append({**base_result, "status": "awaiting_approval",
                                    "director_request_id": work.request_id,
                                    "artifact_hash": artifact.artifact_hash})
                except Exception as exc:
                    issue = self.store.add_issue({"reason": "director_prepare_failed", "kind": lane,
                                                  "detail": str(exc)[:1000], "payload": dict(base_result)})
                    self.store.update_draft(draft_id, {"state": "PARKED", "issues": [*_as_list(record.get("issues")), _compact_store_result(issue)]})
                    results.append({**base_result, "status": "parked", "issue": _compact_store_result(issue)})
                continue
            if not decision.ok:
                issue = self.store.add_issue({
                    "reason": ",".join(decision.blockers),
                    "kind": lane,
                    "payload": dict(base_result),
                })
                self.store.update_draft(draft_id, {
                    "state": "PARKED",
                    "policy": decision_payload,
                    "issues": [*_as_list(record.get("issues")), _compact_store_result(issue)],
                })
                results.append({**base_result, "status": "parked", "issue": _compact_store_result(issue)})
                continue

            if director_scope:
                selected_guid = int(control_config.get("durable_director_player_guid") or 0)
                runtime_guid = (
                    int(runtime["plan"].player_guid) if runtime["kind"] == "plan"
                    else int(runtime["proposals"][0].player.guid)
                )
                if selected_guid <= 0 or selected_guid != int(session["character_guid"]) or runtime_guid != selected_guid:
                    issue = self.store.add_issue({"reason": "director_scope_mismatch", "kind": lane, "payload": dict(base_result)})
                    self.store.update_draft(draft_id, {"state": "PARKED", "issues": [*_as_list(record.get("issues")), _compact_store_result(issue)]})
                    results.append({**base_result, "status": "parked", "issue": _compact_store_result(issue)})
                    continue
                try:
                    from wm.autoplay.director_work import DirectorWorkLedger, FrozenWork

                    ledger = DirectorWorkLedger(settings=settings)
                    artifact = FrozenWork.from_runtime(runtime)
                    work = ledger.prepare(
                        origin_key=f"autoplay:{lane}:{draft_id}", player_guid=selected_guid,
                        lane=lane, artifact=artifact, preview=dry_run_payload,
                        evidence={"draft_id": draft_id, "schema_version": schema_version,
                                  "source_event_at": _draft_source_event_at(record),
                                  "memory_revision": record.get("memory_revision"),
                                  "quest_feasibility": feasibility},
                    )
                    if work.state == "received":
                        work = ledger.authorize(work, policy=decision_payload, mode="automatic")
                    if work.state == "authorized":
                        if record.get("origin") == "autoplay_llm" and self._draft_memory_blocker(
                            record=record, settings=settings, player_guid=selected_guid,
                        ):
                            raise RuntimeError("director_evidence_changed_before_apply")
                        if lane == "quest":
                            from wm.autoplay.quest_feasibility import assess_quest_plan

                            fresh_runtime = work.artifact.thaw()
                            assess_quest_plan(plan=fresh_runtime["plan"], settings=settings)
                            if FrozenWork.from_runtime(fresh_runtime).artifact_hash != work.artifact_hash:
                                raise RuntimeError("director_quest_preview_changed_before_apply")
                        work = ledger.claim(work)
                        try:
                            apply_results = _execute_runtime_work(
                                runtime=work.artifact.thaw(), coordinator=coordinator, mode="apply",
                            )
                            work = ledger.record_result(work, results=apply_results)
                        except BaseException:
                            ledger.mark_uncertain(work, reason="executor_outcome_unknown")
                            raise
                    if work.state in {"dispatching", "uncertain"}:
                        raise RuntimeError(f"director_effect_{work.state}_requires_reconciliation")
                    if work.state not in {"applied", "verified"}:
                        raise RuntimeError(f"director_unexpected_state:{work.state}")
                    apply_payload = {"at": utc_now_iso(), "draft_id": draft_id, "lane": lane,
                                     "status": "applied", "director_request_id": work.request_id,
                                     "artifact_hash": work.artifact_hash, "proof_state": work.state}
                except Exception as exc:
                    issue = self.store.add_issue({"reason": "director_apply_blocked", "kind": lane,
                                                  "detail": str(exc)[:1000], "payload": dict(base_result)})
                    self.store.update_draft(draft_id, {"state": "PARKED", "issues": [*_as_list(record.get("issues")), _compact_store_result(issue)]})
                    results.append({**base_result, "status": "parked", "issue": _compact_store_result(issue)})
                    continue
                for key in idempotency_keys:
                    self.store.mark_idempotency_key(key)
                    seen_idempotency.add(key)
                self.store.update_draft(draft_id, {"state": "APPLIED", "policy": decision_payload,
                                                   "latest_apply": apply_payload})
                results.append({**base_result, "status": "applied", "apply": apply_payload})
                continue

            apply_results = _execute_runtime_work(runtime=runtime, coordinator=coordinator, mode="apply")
            apply_payload = {
                "at": utc_now_iso(),
                "draft_id": draft_id,
                "lane": lane,
                "status": "complete" if _runtime_results_ok(apply_results, expected="applied") else "failed",
                "steps": [_result_to_dict(item) for item in apply_results],
            }
            if apply_payload["status"] == "complete":
                for key in idempotency_keys:
                    self.store.mark_idempotency_key(key)
                    seen_idempotency.add(key)
                lane_counts[lane] = int(lane_counts.get(lane, 0)) + 1
                current = self.store.load_status()
                counters = dict(current.get("counters") or {})
                counters["auto_applied"] = int(counters.get("auto_applied") or 0) + 1
                self.store.update_draft(draft_id, {
                    "state": "APPLIED",
                    "policy": decision_payload,
                    "latest_apply": apply_payload,
                    "counters": counters,
                })
                record_result = {**base_result, "status": "applied", "apply": apply_payload}
                self.store.append_journal("autoplay_apply", record_result)
                results.append(record_result)
            else:
                issue = self.store.add_issue({"reason": "apply_failed", "kind": lane, "payload": {**base_result, "apply": apply_payload}})
                self.store.update_draft(draft_id, {
                    "state": "PARKED",
                    "policy": decision_payload,
                    "latest_apply": apply_payload,
                    "issues": [*_as_list(record.get("issues")), _compact_store_result(issue)],
                })
                results.append({**base_result, "status": "parked", "apply": apply_payload, "issue": _compact_store_result(issue)})
        return results

    def _draft_memory_blocker(self, *, record: dict[str, Any], settings: Settings, player_guid: int) -> str | None:
        from wm.character.memory import load_memory_entries
        from wm.context.pack import build_memory_context_section
        from wm.db.mysql_cli import MysqlCliClient

        if int(record.get("player_guid") or 0) != player_guid:
            return "draft_player_changed"
        expected = str(record.get("memory_revision") or "")
        if not expected:
            return "draft_memory_revision_missing"
        try:
            section = build_memory_context_section(load_memory_entries(
                client=MysqlCliClient(), settings=settings, player_guid=player_guid,
            ))
        except Exception:
            return "draft_memory_unavailable"
        current = _memory_revision(
            active=section["active"], evidence=section["source_evidence"], excluded=section["excluded"],
        )
        return "draft_memory_changed" if current != expected else None

    def _safe_window(self, *, settings: Settings, session: dict[str, Any] | None) -> SafeWindow:
        return SafeWindow(
            client_running=_wow_client_running(),
            scoped_player_online=_is_scoped_player_online(settings=settings, session=session),
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
                "kind": "native_bridge",
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )
        if completed.returncode != 0:
            self.store.add_issue({"reason": "watcher_start_failed", "kind": "watcher", "detail": completed.stderr[-1000:]})
        self._start_addon_log_watcher(config)

    def _start_native_bridge_watcher(self, config: AutoplayRuntimeConfig) -> None:
        script = config.project_root / "scripts" / "bridge_lab" / "Start-BridgeLabNativeWatch.ps1"
        if not script.exists():
            self.store.add_issue({"reason": f"native_watcher_start_missing_script:{script}", "kind": "watcher"})
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
            "-IntervalSeconds",
            "1.0",
            "-BatchSize",
            "50",
            "-LabMySqlPort",
            str(config.bridge_lab_mysql_port),
            "-SoapPort",
            str(config.soap_port),
            "-ArmFromEnd",
        ]
        completed = subprocess.run(args, capture_output=True, text=True, check=False)
        self.store.append_journal(
            "watcher_start",
            {
                "kind": "native_bridge",
                "mode": "chat",
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )
        if completed.returncode != 0:
            self.store.add_issue({"reason": "native_watcher_start_failed", "kind": "watcher", "detail": completed.stderr[-1000:]})

    def _start_addon_log_watcher(self, config: AutoplayRuntimeConfig) -> None:
        if config.player_guid is None:
            return
        root = config.project_root / "artifacts" / "bridge_lab_addon_watch"
        root.mkdir(parents=True, exist_ok=True)
        pid_path = root / "addon_log_watch.pid"
        stdout_path = root / "addon_log_watch.stdout.log"
        stderr_path = root / "addon_log_watch.stderr.log"
        metadata_path = root / "addon_log_watch.json"
        existing_pid = _read_pid(pid_path)
        if existing_pid is not None and _process_exists(existing_pid):
            self.store.append_journal(
                "watcher_start",
                {
                    "kind": "addon_log",
                    "status": "already_running",
                    "pid": existing_pid,
                    "stdout": str(stdout_path),
                    "stderr": str(stderr_path),
                },
            )
            return

        python_exe = config.project_root / ".venv" / "Scripts" / "python.exe"
        executable = str(python_exe) if python_exe.exists() else "python"
        args = [
            executable,
            "-u",
            "-m",
            "wm.events.watch",
            "--adapter",
            "addon_log",
            "--mode",
            "apply",
            "--player-guid",
            str(config.player_guid),
            "--summary",
            "--confirm-live-apply",
            "--interval-seconds",
            "1.0",
            "--batch-size",
            "50",
            "--arm-from-end",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        env["WM_WORLD_DB_PORT"] = str(config.bridge_lab_mysql_port)
        env["WM_CHAR_DB_PORT"] = str(config.bridge_lab_mysql_port)
        env["WM_SOAP_PORT"] = str(config.soap_port)
        creationflags = 0
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creationflags |= subprocess.DETACHED_PROCESS
        try:
            stdout_handle = stdout_path.open("a", encoding="utf-8")
            stderr_handle = stderr_path.open("a", encoding="utf-8")
            process = subprocess.Popen(
                args,
                cwd=str(config.project_root),
                env=env,
                stdout=stdout_handle,
                stderr=stderr_handle,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            stdout_handle.close()
            stderr_handle.close()
        except Exception as exc:
            self.store.add_issue({"reason": "addon_log_watcher_start_failed", "kind": "watcher", "detail": str(exc)[:1000]})
            return

        pid_path.write_text(str(process.pid), encoding="utf-8")
        metadata = {
            "pid": process.pid,
            "started_at": utc_now_iso(),
            "player_guid": int(config.player_guid),
            "adapter": "addon_log",
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        time.sleep(1)
        if process.poll() is not None:
            detail = stderr_path.read_text(encoding="utf-8", errors="replace")[-1000:] if stderr_path.exists() else ""
            self.store.add_issue({"reason": "addon_log_watcher_exited", "kind": "watcher", "detail": detail})
            return
        self.store.append_journal(
            "watcher_start",
            {
                "kind": "addon_log",
                "status": "started",
                "pid": process.pid,
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
            },
        )


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


def _config_to_dict(config: AutoplayRuntimeConfig) -> dict[str, Any]:
    return {
        "bridge_lab_mysql_port": int(config.bridge_lab_mysql_port),
        "soap_port": int(config.soap_port),
        "llm_enabled": bool(config.llm_enabled),
        "llm_chat_enabled": bool(config.llm_chat_enabled),
        "llm_lanes": list(config.llm_lanes),
        "llm_event_age_seconds": int(config.llm_event_age_seconds),
        "llm_cooldown_seconds": int(config.llm_cooldown_seconds),
        "llm_events_per_tick": int(config.llm_events_per_tick),
        "llm_ambient_narration_enabled": bool(config.llm_ambient_narration_enabled),
        "llm_ambient_cooldown_seconds": int(config.llm_ambient_cooldown_seconds),
        "llm_conversation_memory_enabled": bool(config.llm_conversation_memory_enabled),
        "llm_scene_director_enabled": bool(config.llm_scene_director_enabled),
        "durable_native_intent_enabled": bool(config.durable_native_intent_enabled),
        "durable_director_enabled": bool(config.durable_director_enabled),
        "durable_director_player_guid": config.durable_director_player_guid,
        "initiative_preset": config.initiative_preset,
        "activity_proposals_enabled": config.activity_proposals_enabled,
        "llm_model": config.llm_model,
        "llm_base_url": config.llm_base_url,
    }


def _merged_control_config(
    *,
    config: AutoplayRuntimeConfig,
    status: dict[str, Any],
    command: dict[str, Any],
) -> dict[str, Any]:
    merged = _config_to_dict(config)
    if isinstance(status.get("config"), dict):
        merged.update({key: value for key, value in status["config"].items() if value is not None})
    if isinstance(command.get("config"), dict):
        merged.update({key: value for key, value in command["config"].items() if value is not None})
    runtime_config = _config_to_dict(config)
    for key in ("llm_model", "llm_base_url"):
        if runtime_config.get(key) not in (None, ""):
            merged[key] = runtime_config[key]
    if config.durable_director_enabled:
        merged["durable_director_enabled"] = True
    if config.durable_director_player_guid is not None:
        merged["durable_director_player_guid"] = int(config.durable_director_player_guid)
    merged["llm_enabled"] = bool(merged.get("llm_enabled", True))
    merged["llm_chat_enabled"] = bool(merged.get("llm_chat_enabled", True))
    merged["llm_lanes"] = _normalize_lanes(merged.get("llm_lanes"))
    merged["llm_event_age_seconds"] = int(merged.get("llm_event_age_seconds") or 300)
    merged["llm_cooldown_seconds"] = int(merged.get("llm_cooldown_seconds") or 60)
    merged["llm_events_per_tick"] = max(int(merged.get("llm_events_per_tick") or 1), 1)
    merged["llm_ambient_narration_enabled"] = bool(merged.get("llm_ambient_narration_enabled", True))
    merged["llm_ambient_cooldown_seconds"] = int(merged.get("llm_ambient_cooldown_seconds") or 150)
    merged["llm_conversation_memory_enabled"] = bool(merged.get("llm_conversation_memory_enabled", True))
    merged["llm_scene_director_enabled"] = bool(merged.get("llm_scene_director_enabled", True))
    merged["durable_native_intent_enabled"] = bool(merged.get("durable_native_intent_enabled", False))
    merged["durable_director_enabled"] = bool(merged.get("durable_director_enabled", False))
    merged["initiative_preset"] = str(merged.get("initiative_preset") or "moderate")
    if merged["initiative_preset"] not in {"on_demand", "moderate", "active"}:
        raise ValueError("initiative_preset must be on_demand, moderate or active")
    merged["activity_proposals_enabled"] = bool(merged.get("activity_proposals_enabled", True))
    merged["llm_chat_context_epoch"] = int(merged.get("llm_chat_context_epoch") or 0)
    return merged


def _disabled_llm_status(control_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "disabled": True,
        "base_url": control_config.get("llm_base_url") or "http://localhost:1234/v1",
        "model": control_config.get("llm_model"),
        "models": [],
        "error": "LLM autoplay is disabled.",
    }


def _normalize_lanes(raw: Any) -> list[str]:
    if isinstance(raw, str):
        items = [item.strip() for item in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        items = [str(item).strip() for item in raw]
    else:
        items = ["scene", "action"]
    supported = {"quest", "item", "spell", "ability", "scene", "action", "chat"}
    normalized = [item for item in items if item in supported]
    return normalized or ["scene", "action"]


def _cooldown_active(latest_proposal: Any, *, seconds: int) -> bool:
    if seconds <= 0 or not isinstance(latest_proposal, dict):
        return False
    at = latest_proposal.get("at") or latest_proposal.get("created_at")
    if not at:
        return False
    parsed = _parse_time(str(at))
    if parsed is None:
        return False
    return (datetime.now(timezone.utc) - parsed).total_seconds() < seconds


def _opportunity_from_event(
    *,
    event: Any,
    lanes: list[str],
    max_event_age_seconds: int,
    force_lane: str | None = None,
) -> dict[str, Any] | None:
    event_payload = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    occurred = _parse_time(str(event_payload.get("occurred_at") or ""))
    if occurred is not None:
        age = (datetime.now(timezone.utc) - occurred).total_seconds()
        if age > max_event_age_seconds:
            return None
    lane = force_lane or _select_lane_for_event(str(event_payload.get("event_type") or ""), lanes)
    if lane is None:
        return None
    try:
        schema_version = schema_for_lane(lane)
    except KeyError:
        return None
    source_key = str(event_payload.get("source_event_key") or event_payload.get("event_id") or "event")
    stable_key = _stable_key(f"{event_payload.get('source')}:{source_key}:{lane}")
    return {
        "opportunity_id": f"{stable_key}-{lane}",
        "stable_key": stable_key,
        "lane": lane,
        "schema_version": schema_version,
        "player_guid": event_payload.get("player_guid"),
        "source_event": event_payload,
        "source_event_at": event_payload.get("occurred_at"),
        "source_event_key": source_key,
        "status": "candidate",
        "risk": "low",
    }


def _select_lane_for_event(event_type: str, lanes: list[str]) -> str | None:
    preferences = {
        "kill": ["scene", "action", "quest"],
        "talk": ["scene", "action", "quest"],
        "gossip_select": ["scene", "action", "quest"],
        "quest_complete": ["quest", "scene", "item", "action"],
        "quest_completed": ["quest", "scene", "item", "action"],
        "quest_rewarded": ["item", "scene", "quest", "action"],
        "loot_item": ["item", "scene", "action"],
        "item_use": ["item", "spell", "scene", "action"],
        "spell_cast": ["ability", "spell", "scene", "action"],
        "aura_applied": ["ability", "scene", "action"],
        "aura_removed": ["scene", "action"],
        "enter_area": ["scene", "action", "quest"],
    }.get(event_type, ["scene", "action"])
    for lane in preferences:
        if lane in lanes:
            return lane
    return lanes[0] if lanes else None


def _deterministic_facts(
    *,
    opportunity: dict[str, Any],
    player_guid: int,
    control_config: dict[str, Any],
) -> dict[str, Any]:
    stable_key = str(opportunity.get("stable_key") or "autoplay")
    try:
        suffix = int(stable_key[:6], 16) if stable_key[:6] else 0
    except ValueError:
        suffix = int(hashlib.sha256(stable_key.encode()).hexdigest()[:6], 16)
    source_event = opportunity.get("source_event") if isinstance(opportunity.get("source_event"), dict) else {}
    return {
        "player_guid": int(player_guid),
        "stable_key": stable_key,
        "source_event": source_event,
        "max_event_age_seconds": int(control_config.get("llm_event_age_seconds") or 300),
        "item_entry": 910000 + (suffix % 800),
        "spell_entry": 947000 + (suffix % 800),
        "allowed_native_action_kinds": ["player_chat_message"],
        "allowed_shell_families": ["self_aura", "unit_target_effect", "unit_target_projectile"],
    }


def _instruction_for_opportunity(opportunity: dict[str, Any]) -> str:
    lane = str(opportunity.get("lane") or "scene")
    if opportunity.get("schema_version") == "wm.quest.release.material_delivery.v1":
        return (
            "Draft an optional material delivery tied to the supplied gathering activity or player request. "
            "Select item_entry only from delivery candidates. The host owns IDs, quantity, NPC, payment and directions. "
            "Write a short fitting title, narrative and reward acknowledgement. Do not claim the player's purpose is certain. "
            "This is an offer at an NPC, not a forced quest grant. Existing materials qualify and are consumed."
        )
    if lane == "quest" and opportunity.get("player_request"):
        return (
            f"Draft one playable, low-risk kill quest for this exact player request: "
            f"{str(opportunity['player_request'])[:800]}. The host will reject unverified target hostility, "
            "insufficient spawns, inaccessible turn-ins, and missing rewards. Do not invent IDs; "
            "use only target and questgiver facts in the evidence packet."
        )
    event = opportunity.get("source_event") if isinstance(opportunity.get("source_event"), dict) else {}
    event_type = str(event.get("event_type") or "event")
    return (
        f"Draft exactly one low-risk WM {lane} reaction to the fresh {event_type} event. "
        "Use only the requested JSON schema. Keep it scoped to the supplied player. "
        "Do not include SQL, GM commands, shell commands, file edits, config edits, or direct mutation instructions. "
        "Prefer subtle in-world feedback over large rewards. Use rollback/audit-friendly choices."
    )


def _compact_autoplay_context(context_pack: dict[str, Any], *, opportunity: dict[str, Any], player_guid: int) -> dict[str, Any]:
    source_event = opportunity.get("source_event") if isinstance(opportunity.get("source_event"), dict) else {}
    pack_guid = context_pack.get("player_guid")
    if pack_guid is not None and int(pack_guid) != int(player_guid):
        raise ValueError("session context belongs to another player")
    character_state = dict(context_pack.get("character_state")) if isinstance(context_pack.get("character_state"), dict) else {}
    character_state.pop("notes", None)
    if isinstance(context_pack.get("memory"), list):
        character_state["conversation_steering"] = context_pack["memory"]
    player = _compact_context_value(
        _first_present(context_pack, "player", "character", "session", default={}), depth=2
    )
    if not player:
        player = {"guid": int(player_guid), "profile": _compact_context_value(character_state.get("profile"), depth=3)}
    memory = context_pack.get("memory") if isinstance(context_pack.get("memory"), list) else []
    recent_events = context_pack.get("recent_events") if isinstance(context_pack.get("recent_events"), list) else []
    return {
        "player_guid": int(player_guid),
        "player": player if isinstance(player, dict) else {},
        "context_status": context_pack.get("status"),
        "context_notes": [f"{note.split(':', 1)[0]}:unavailable" for note in context_pack.get("notes", []) if isinstance(note, str)],
        "character_state": _compact_context_value(character_state, depth=4),
        "memory": [_compact_context_value(entry, depth=3) for entry in memory if isinstance(entry, dict)],
        "recent_events": [_compact_event(entry) for entry in recent_events[:5] if isinstance(entry, dict)],
        "native_context_snapshot": _compact_context_value(context_pack.get("native_context_snapshot"), depth=4),
        "source_event": _compact_event(source_event),
        "lane": opportunity.get("lane"),
        "stable_key": opportunity.get("stable_key"),
        "allowed_native_action_kinds": ["player_chat_message"],
        "style": "grounded in observed play and character history; no SQL, GM commands, shell commands, or file edits",
        "wm_tools": autoplay_tool_manifest(),
    }


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "event_value": event.get("event_value"),
        "occurred_at": event.get("occurred_at"),
        "source": event.get("source"),
        "source_event_key": event.get("source_event_key"),
        "subject_type": event.get("subject_type"),
        "subject_entry": event.get("subject_entry"),
        "subject_name": payload.get("subject_name") or payload.get("aura_name") or payload.get("spell_name"),
        "zone_id": event.get("zone_id"),
        "area_id": event.get("area_id"),
    }


def _compact_opportunity_for_llm(opportunity: dict[str, Any]) -> dict[str, Any]:
    compact = {
        key: opportunity.get(key)
        for key in ("opportunity_id", "stable_key", "lane", "schema_version", "player_guid", "source_event_at", "source_event_key", "risk")
    }
    if opportunity.get("player_request"):
        compact["player_request"] = str(opportunity["player_request"])[:1000]
    source_event = opportunity.get("source_event") if isinstance(opportunity.get("source_event"), dict) else {}
    compact["source_event"] = _compact_event(source_event)
    return compact


def _compact_intent(intent: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(intent, dict):
        return None
    args = intent.get("args") if isinstance(intent.get("args"), dict) else {}
    return {
        "verb": str(intent.get("verb") or "")[:128],
        "reason": str(intent.get("reason") or "")[:300],
        "args_keys": sorted(str(key) for key in args.keys())[:20],
    }


def _first_present(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _compact_context_value(value: Any, *, depth: int) -> Any:
    if depth <= 0:
        return None
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for key, item in list(value.items())[:20]:
            if key in {"raw", "rows", "events", "history", "inventory", "spells", "quests"}:
                continue
            compact[str(key)] = _compact_context_value(item, depth=depth - 1)
        return compact
    if isinstance(value, list):
        return [_compact_context_value(item, depth=depth - 1) for item in value[:5]]
    if isinstance(value, str):
        return value[:500]
    return value


def _chat_action_proposal(*, player_guid: int, message: str, source_message: str) -> Any:
    from wm.control.models import ControlProposal

    stable = _stable_key(f"{player_guid}:{source_message}:{message}:{utc_now_iso()}")
    return ControlProposal.model_validate(
        {
            "schema_version": "control.proposal.v1",
            "source_event": None,
            "player": {"guid": int(player_guid)},
            "selected_recipe": "manual_admin_action",
            "action": {
                "kind": "native_bridge_action",
                "payload": {
                    "native_action_kind": "player_chat_message",
                    "payload": {
                        "message": str(message)[:_CHAT_PART_LIMIT],
                        "style": "channel",
                        "channel_name": "WM",
                        "sender_name": "WorldMaster",
                    },
                    "created_by": "wm.autoplay.chat",
                    "risk_level": "low",
                    "expires_seconds": 60,
                },
            },
            "rationale": "Reply to a direct player WM chat prompt.",
            "risk": {"level": "low", "irreversible": False, "notes": []},
            "idempotency_key": f"autoplay:chat:{stable}",
            "author": {
                "kind": "manual_admin",
                "name": "wm.autoplay",
                "manual_reason": "policy-approved direct WM chat reply",
            },
            "metadata": {"source_message": str(source_message)[:1000], "lane": "chat"},
        }
    )


def _ingest_recent_native_bridge_chat(*, client: Any, settings: Settings, store: Any, limit: int = 100) -> None:
    from wm.events.models import WMEvent

    try:
        rows = client.query(
            host=settings.world_db_host,
            port=settings.world_db_port,
            user=settings.world_db_user,
            password=settings.world_db_password,
            database=settings.world_db_name,
            sql=(
                "SELECT BridgeEventID, OccurredAt, Source, PlayerGUID, AccountID, SubjectType, SubjectGUID, "
                "SubjectEntry, MapID, ZoneID, AreaID, PayloadJSON "
                "FROM wm_bridge_event "
                "WHERE EventFamily = 'chat' AND EventType IN ('wm_chat', 'wmchat', 'towm') "
                "ORDER BY BridgeEventID DESC "
                f"LIMIT {int(limit)}"
            ),
        )
    except Exception:
        return

    events: list[WMEvent] = []
    for row in reversed(rows):
        payload = _parse_json_dict(row.get("PayloadJSON"))
        message = _first_text(payload.get("message")) if payload else None
        if not message:
            continue
        bridge_event_id = _int_or_none(row.get("BridgeEventID"))
        if bridge_event_id is None:
            continue
        player_guid = _int_or_none(row.get("PlayerGUID"))
        events.append(
            WMEvent(
                event_class="observed",
                event_type="wm_chat",
                source="native_bridge",
                source_event_key=f"native_bridge:{bridge_event_id}",
                occurred_at=str(row.get("OccurredAt") or ""),
                player_guid=player_guid,
                subject_type=_first_text(row.get("SubjectType")) or "player",
                subject_entry=_int_or_none(row.get("SubjectEntry")) or player_guid,
                map_id=_int_or_none(row.get("MapID")),
                zone_id=_int_or_none(row.get("ZoneID")),
                area_id=_int_or_none(row.get("AreaID")),
                event_value=message,
                metadata={
                    "bridge_event_id": bridge_event_id,
                    "raw_event_family": "chat",
                    "raw_event_type": "wm_chat",
                    "account_id": _int_or_none(row.get("AccountID")),
                    "subject_guid": _first_text(row.get("SubjectGUID")),
                    "payload": payload,
                },
            )
        )
    if events:
        store.record(events)
