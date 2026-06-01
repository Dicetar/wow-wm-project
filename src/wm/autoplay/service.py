from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timezone
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from wm.autoplay.ambient import build_ambient_messages
from wm.autoplay.ambient import classify_ambient_event
from wm.autoplay.ambient import HIGH_PRIORITY_AMBIENT_KINDS
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
    llm_model: str | None = None
    llm_base_url: str | None = None


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

    def tick(self, *, config: AutoplayRuntimeConfig) -> dict[str, Any]:
        command = self.store.load_command()
        status = self.store.load_status()
        control_config = _merged_control_config(config=config, status=status, command=command)
        counters = dict(status.get("counters") or {})
        counters["ticks"] = int(counters.get("ticks") or 0) + 1

        stop_requested = bool(command.get("stop_requested") or status.get("stop_requested"))
        paused = bool(command.get("paused") or status.get("paused"))
        settings = Settings.from_env()
        readiness = self._readiness(settings)
        session = self._active_session(config=config)
        llm_enabled = bool(control_config.get("llm_enabled", True))
        llm = self._llm_health(control_config) if llm_enabled else _disabled_llm_status(control_config)
        safe_window = self._safe_window(session=session)
        generation_results: list[dict[str, Any]] = []
        apply_results: list[dict[str, Any]] = []
        if not stop_requested and not paused and llm_enabled:
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
                return {"message": reply, "raw_content": content, "source": "llm",
                        "model": settings.model, "intent": extracted_intent or intent}
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
    ) -> dict[str, Any] | None:
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
            )
        except Exception:
            return None

    def _chat_world_context(
        self,
        *,
        settings: Settings,
        player_guid: int,
        message: str,
        source_event: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return build_chat_world_context(
                settings=settings,
                player_guid=int(player_guid),
                message=message,
                source_event=source_event,
            )
        except Exception as exc:
            return {
                "schema_version": "wm.autoplay.chat_world_context.v1",
                "speaker": {"guid": int(player_guid), "message": str(message)[:1000]},
                "source_event": source_event,
                "notes": [f"world_context_failed: {type(exc).__name__}: {exc}"],
            }

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
        settings = Settings.from_env()
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
        settings = Settings.from_env()
        readiness = self._readiness(settings)
        session = self._active_session(config=config)
        llm = self._llm_health(control_config)
        if not readiness.get("ok"):
            return {"ok": False, "error": "readiness_not_green", "readiness": readiness}
        if not llm.get("ok"):
            return {"ok": False, "error": "llm_unavailable", "llm": llm}
        if not session or session.get("character_guid") in (None, ""):
            return {"ok": False, "error": "no_active_session"}
        player_guid = int(session["character_guid"])
        resolved = self._resolve_pending_if_yes_no(
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
        if _looks_like_scene_request(message):
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
        resolved = self._resolve_pending_if_yes_no(
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
            if _looks_like_scene_request(message):
                scene_result = self._handle_scene_request(
                    settings=settings, control_config=control_config, player_guid=player_guid,
                    message=message, world_context=world_context)
            if scene_result is not None:
                result["scene_result"] = scene_result
            elif reply.get("intent"):
                result["intent_result"] = self._handle_intent(
                    settings=settings, control_config=control_config, player_guid=player_guid,
                    intent=reply["intent"], source_message=message)
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
    ) -> dict[str, Any]:
        from wm.autoplay.intent import IntentRejection, compile_intent

        verb = str(intent.get("verb") or "")
        intent_args = intent.get("args") if isinstance(intent.get("args"), dict) else {}

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
                self.store.add_issue({
                    "reason": "spawn_args_unresolved", "kind": "intent",
                    "detail": prepared.reason,
                    "payload": {"intent": intent, "player_guid": int(player_guid)},
                })
                self._speak(settings=settings, player_guid=player_guid,
                            text="I could not bring that creature forth just now.",
                            source_message=source_message)
                return {"intent": "rejected", "reason": prepared.reason}
            intent_args = prepared

        compiled = compile_intent(
            player_guid=player_guid,
            verb=verb,
            args=intent_args,
            modes=control_config.get("conversational_verb_modes"),
            reason=str(intent.get("reason") or ""),
        )
        if isinstance(compiled, IntentRejection):
            self.store.add_issue({
                "reason": "intent_rejected", "kind": "intent",
                "detail": compiled.reason,
                "payload": {"intent": intent, "player_guid": int(player_guid)},
            })
            return {"intent": "rejected", "reason": compiled.reason}
        coordinator = self._control_coordinator(settings)
        dry = coordinator.execute(proposal=compiled.proposal, mode="dry-run", confirm_live_apply=False)
        if dry.status != "dry-run":
            self.store.add_issue({
                "reason": "intent_dry_run_failed", "kind": "intent",
                "detail": _result_to_dict(dry), "payload": {"verb": compiled.verb},
            })
            self._speak(settings=settings, player_guid=player_guid,
                        text=f"I cannot do that right now ({compiled.verb.replace('_', ' ')}).",
                        source_message=source_message)
            return {"intent": "dry_run_failed", "verb": compiled.verb}
        if compiled.mode == "auto":
            return self._apply_compiled(settings=settings, player_guid=player_guid,
                                        compiled=compiled, source_message=source_message)
        # confirm mode -> park pending, surfaced in chat + panel inbox (same record)
        self.store.set_pending_intent(player_guid, {
            "verb": compiled.verb,
            "risk": compiled.risk,
            "summary": intent.get("reason") or compiled.verb,
            "proposal": compiled.proposal.model_dump(mode="json"),
        }, ttl_seconds=120)
        self._speak(settings=settings, player_guid=player_guid,
                    text=f"I can {compiled.verb.replace('_', ' ')} - say yes to confirm.",
                    source_message=source_message)
        return {"intent": "pending", "verb": compiled.verb}

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
        applier = CharacterJourneyStore(client=MysqlCliClient(), settings=settings)
        result = applier.apply_plan(plan=plan, mode="apply")
        self.store.append_journal("conversation_memory", {
            "at": utc_now_iso(),
            "player_guid": int(player_guid),
            "note": note,
            "ok": bool(getattr(result, "ok", False)),
            "error": getattr(result, "error", None),
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
        coordinator = self._control_coordinator(settings)
        applied = coordinator.execute(proposal=compiled.proposal, mode="apply", confirm_live_apply=True)
        record = {
            "at": utc_now_iso(),
            "player_guid": int(player_guid),
            "verb": compiled.verb,
            "risk": compiled.risk,
            "source_message": source_message,
            "apply": _result_to_dict(applied),
        }
        self.store.append_journal("deed", record)
        ok = applied.status == "applied"
        counters_status = self.store.load_status()
        counters = dict(counters_status.get("counters") or {})
        counters["auto_applied"] = int(counters.get("auto_applied") or 0) + (1 if ok else 0)
        self.store.update_status(counters=counters)
        msg = (f"Done - {compiled.verb.replace('_', ' ')}." if ok
               else f"That did not take ({compiled.verb.replace('_', ' ')}).")
        self._speak(settings=settings, player_guid=player_guid, text=msg, source_message=source_message)
        if not ok:
            self.store.add_issue({"reason": "intent_apply_failed", "kind": "intent", "detail": record})
        return {"intent": "applied" if ok else "apply_failed", "verb": compiled.verb}

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
        self.store.clear_pending_intent(player_guid, reason="player_confirmed")
        return self._apply_compiled(settings=settings, player_guid=player_guid,
                                    compiled=compiled, source_message=source_message)

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
            step_results.append({"index": index, "verb": verb, "status": status_value})
            if status_value != "applied":
                ok_all = False
                break
        record = {
            "at": utc_now_iso(),
            "player_guid": int(player_guid),
            "scene_name": scene_name,
            "steps_total": len(steps),
            "steps_executed": len(step_results),
            "ok": ok_all,
            "step_results": step_results,
        }
        self.store.append_journal("scene_run", record)
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
            if not ready_for_llm and not _is_forget_context_command(message):
                continue
            result = self._reply_to_chat_event(
                control_config=control_config,
                settings=settings,
                session=session,
                event_payload=event_payload,
            )
            chat_results.append(result)
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
        for event in events:
            source_key = str(getattr(event, "source_event_key", "") or "")
            if not source_key or source_key in seen:
                continue
            if getattr(event, "player_guid", None) not in (None, session_guid):
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
            results.append(
                self._generate_for_opportunity(
                    control_config=control_config,
                    readiness=readiness,
                    session=session,
                    llm=llm,
                    opportunity=opportunity,
                )
            )
            source_key = str((opportunity.get("source_event") or {}).get("source_event_key") or "")
            if source_key:
                self.store.mark_event_seen(source_key)
        return results

    def _generate_for_opportunity(
        self,
        *,
        control_config: dict[str, Any],
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
        context_pack = _compact_autoplay_context(
            build_session_context_pack(player_guid=player_guid),
            opportunity=opportunity,
            player_guid=player_guid,
        )
        facts = _deterministic_facts(opportunity=opportunity, player_guid=player_guid, control_config=control_config)
        result = adapter.generate(
            schema_version=schema_version,
            instruction=_instruction_for_opportunity(opportunity),
            context_pack=context_pack,
            candidate_pack={
                "opportunity": _compact_opportunity_for_llm(opportunity),
                "policy": self.policy.to_dict(),
                "wm_tools": autoplay_tool_manifest(),
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
            "instruction": _instruction_for_opportunity(opportunity),
            "parsed_json": result.draft,
            "issues": result.issues,
            "request": _compact_request(result.request),
            "raw_content": result.raw_content,
        }
        if result.ok:
            saved = self.store.add_draft(record)
            self.panel_state.save_draft({**record, "validation": {"ok": True, "issues": []}})
            return {"ok": True, "draft_id": saved["draft_id"], "lane": opportunity.get("lane"), "schema_version": schema_version}
        issue = self.store.add_issue({
            "reason": "llm_draft_invalid",
            "kind": str(opportunity.get("lane") or "llm"),
            "detail": "; ".join(str(item.get("message")) for item in result.issues[:3]) if result.issues else "unknown",
            "payload": record,
        })
        return {"ok": False, "draft_id": draft_id, "lane": opportunity.get("lane"), "issue": _compact_store_result(issue)}

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
        if not bool(control_config.get("llm_ambient_narration_enabled", True)):
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
        del control_config
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
            try:
                runtime = _runtime_work_from_draft(record=record, settings=settings)
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
    suffix = int(stable_key[:6], 16) if stable_key[:6] else 0
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
    player = _compact_context_value(_first_present(context_pack, "player", "character", "session", default={}), depth=2)
    return {
        "player_guid": int(player_guid),
        "player": player if isinstance(player, dict) else {},
        "source_event": _compact_event(source_event),
        "lane": opportunity.get("lane"),
        "stable_key": opportunity.get("stable_key"),
        "allowed_native_action_kinds": ["player_chat_message"],
        "style": "subtle in-world feedback; no rewards, SQL, GM commands, shell commands, or file edits",
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
    source_event = opportunity.get("source_event") if isinstance(opportunity.get("source_event"), dict) else {}
    compact["source_event"] = _compact_event(source_event)
    return compact


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


def _runtime_proposals_from_draft(record: dict[str, Any]) -> list[Any]:
    lane = str(record.get("lane") or "")
    payload = record.get("parsed_json") if isinstance(record.get("parsed_json"), dict) else {}
    if lane == "action":
        return [_runtime_action_proposal(record=record, payload=payload)]
    if lane == "scene":
        return _runtime_scene_proposals(record=record, payload=payload)
    raise ValueError(f"Unsupported autoplay runtime lane: {lane}")


def _runtime_work_from_draft(*, record: dict[str, Any], settings: Settings) -> dict[str, Any]:
    lane = str(record.get("lane") or "")
    if lane in {"scene", "action"}:
        return {"kind": "control", "proposals": _runtime_proposals_from_draft(record)}
    if lane in {"quest", "item", "spell"}:
        return {"kind": "plan", "plan": _runtime_publish_plan_from_draft(record=record, settings=settings)}
    if lane == "ability":
        return {
            "kind": "maintenance",
            "reason": "shell_ability_dbc_publish_requires_safe_window_and_shell_template_driver",
        }
    raise ValueError(f"Unsupported autoplay runtime lane: {lane}")


def _execute_runtime_work(*, runtime: dict[str, Any], coordinator: Any, mode: str) -> list[Any]:
    if runtime.get("kind") == "control":
        return [
            coordinator.execute(proposal=proposal, mode=mode, confirm_live_apply=(mode == "apply"))
            for proposal in runtime.get("proposals", [])
        ]
    if runtime.get("kind") == "plan":
        plan = runtime["plan"]
        executor = getattr(coordinator, "executor")
        if mode == "dry-run":
            return [executor.preview(plan=plan)]
        return [executor.execute(plan=plan, mode="apply")]
    raise ValueError(f"Unsupported runtime work kind: {runtime.get('kind')}")


def _runtime_results_ok(results: list[Any], *, expected: str) -> bool:
    if not results:
        return False
    allowed = {"dry-run": {"dry-run", "preview"}, "applied": {"applied"}}[expected]
    return all(str(getattr(result, "status", "")) in allowed for result in results)


def _runtime_idempotency_keys(runtime: dict[str, Any]) -> list[str]:
    if runtime.get("kind") == "control":
        return [
            str(proposal.idempotency_key)
            for proposal in runtime.get("proposals", [])
            if getattr(proposal, "idempotency_key", None)
        ]
    if runtime.get("kind") == "plan":
        plan = runtime["plan"]
        return [str(getattr(plan, "plan_key", ""))]
    return []


def _runtime_rollback_available(lane: str) -> bool:
    return lane in {"quest", "item", "spell", "scene", "action"}


def _runtime_publish_plan_from_draft(*, record: dict[str, Any], settings: Settings) -> Any:
    from wm.db.mysql_cli import MysqlCliClient
    from wm.events.models import PlannedAction
    from wm.events.models import ReactionPlan
    from wm.events.models import SubjectRef
    from wm.reserved.db_allocator import ReservedSlotDbAllocator

    payload = dict(record.get("parsed_json") if isinstance(record.get("parsed_json"), dict) else {})
    lane = str(record.get("lane") or "")
    player_guid = int(record.get("player_guid") or payload.get("player_guid") or 0)
    if player_guid <= 0:
        raise ValueError(f"{lane} draft is missing player_guid")
    opportunity = record.get("opportunity") if isinstance(record.get("opportunity"), dict) else {}
    source_event = opportunity.get("source_event") if isinstance(opportunity.get("source_event"), dict) else {}
    subject = SubjectRef(
        subject_type=str(source_event.get("subject_type") or lane),
        subject_entry=int(source_event.get("subject_entry") or _entry_from_payload(payload, lane) or 0),
    )
    allocator = ReservedSlotDbAllocator(client=MysqlCliClient(), settings=settings)
    actions: list[Any] = []
    if lane == "quest":
        quest_payload = _quest_publish_payload_from_release(payload, record=record, allocator=allocator)
        actions.append(PlannedAction(kind="quest_publish", payload=quest_payload, description="Autoplay publishes an LLM-authored repeatable bounty."))
        if str(quest_payload.get("grant_mode") or "") == "direct_grant":
            actions.append(
                PlannedAction(
                    kind="quest_grant",
                    payload={
                        "quest_id": int(quest_payload["quest_id"]),
                        "player_guid": player_guid,
                        "quest": {"id": int(quest_payload["quest_id"]), "title": quest_payload.get("title")},
                        "player": {"guid": player_guid},
                        "subject": {
                            "type": subject.subject_type,
                            "entry": subject.subject_entry,
                            "name": (quest_payload.get("objective") or {}).get("target_name"),
                        },
                        "turn_in_npc": {
                            "entry": quest_payload.get("end_npc_entry") or quest_payload.get("questgiver_entry"),
                            "name": quest_payload.get("questgiver_name"),
                        },
                    },
                    description="Autoplay grants the newly published quest to the active character.",
                )
            )
    elif lane == "item":
        actions.append(
            PlannedAction(
                kind="item_publish",
                payload=_item_publish_payload_from_release(payload, record=record, allocator=allocator),
                description="Autoplay publishes an LLM-authored managed item.",
            )
        )
    elif lane == "spell":
        actions.append(
            PlannedAction(
                kind="spell_publish",
                payload=_spell_publish_payload_from_release(payload, record=record, allocator=allocator),
                description="Autoplay publishes an LLM-authored managed spell.",
            )
        )
    else:
        raise ValueError(f"Unsupported publish lane: {lane}")
    return ReactionPlan(
        plan_key=f"autoplay:{lane}:{record.get('draft_id')}",
        opportunity_type=f"autoplay_{lane}_publish",
        rule_type=f"autoplay_{lane}",
        player_guid=player_guid,
        subject=subject,
        actions=actions,
        metadata={
            "autoplay_draft_id": record.get("draft_id"),
            "autoplay_schema_version": record.get("schema_version"),
            "source_event_key": opportunity.get("source_event_key"),
        },
    )


def _quest_publish_payload_from_release(payload: dict[str, Any], *, record: dict[str, Any], allocator: Any) -> dict[str, Any]:
    quest = payload.get("quest") if isinstance(payload.get("quest"), dict) else {}
    objective = payload.get("objective") if isinstance(payload.get("objective"), dict) else {}
    reward = payload.get("reward") if isinstance(payload.get("reward"), dict) else {}
    player_guid = int(payload.get("player_guid") or record.get("player_guid") or 0)
    quest_id = _int_or_none(quest.get("quest_id"))
    if quest_id is None:
        slot = allocator.peek_next_free_slot(entity_type="quest")
        if slot is None:
            raise ValueError("No free managed quest slot is available.")
        quest_id = int(slot.reserved_id)
    questgiver_entry = int(quest.get("questgiver_entry") or quest.get("start_npc_entry") or quest.get("end_npc_entry") or 240)
    questgiver_name = str(quest.get("questgiver_name") or "World Master")
    target_entry = int(objective.get("target_entry") or 1)
    target_name = str(objective.get("target_name") or f"Target {target_entry}")
    title = str(quest.get("title") or f"WM Bounty: {target_name}")[:80]
    return {
        "quest_id": quest_id,
        "quest_level": int(quest.get("quest_level") or 70),
        "min_level": min(int(quest.get("min_level") or 1), int(quest.get("quest_level") or 70)),
        "questgiver_entry": questgiver_entry,
        "questgiver_name": questgiver_name,
        "start_npc_entry": _int_or_none(quest.get("start_npc_entry")) or questgiver_entry,
        "end_npc_entry": _int_or_none(quest.get("end_npc_entry")) or questgiver_entry,
        "grant_mode": str(quest.get("grant_mode") or "direct_grant"),
        "title": title,
        "quest_description": str(quest.get("quest_description") or f"The world has marked {target_name}. Cull them."),
        "objective_text": str(quest.get("objective_text") or f"Slay {int(objective.get('kill_count') or 3)} {target_name}."),
        "offer_reward_text": str(quest.get("offer_reward_text") or "The world acknowledges your answer."),
        "request_items_text": str(quest.get("request_items_text") or "Return when the work is done."),
        "objective": {
            "target_entry": target_entry,
            "target_name": target_name,
            "kill_count": int(objective.get("kill_count") or 3),
        },
        "reward": _quest_reward_payload(reward),
        "tags": ["wm_autoplay", "llm_draft"],
        "template_defaults": dict(quest.get("template_defaults") or {"SpecialFlags": 1}),
        "_wm_reserved_slot": {
            "entity_type": "quest",
            "reserved_id": quest_id,
            "arc_key": "wm_autoplay",
            "character_guid": player_guid,
            "notes": [f"draft:{record.get('draft_id')}"],
        },
    }


def _quest_reward_payload(reward: dict[str, Any]) -> dict[str, Any]:
    kind = str(reward.get("kind") or "none")
    result = {"money_copper": 0, "reward_item_count": int(reward.get("item_count") or 1)}
    if kind == "money":
        result["money_copper"] = int(reward.get("money_copper") or 0)
    elif kind == "item" and reward.get("item_entry") not in (None, ""):
        result["reward_item_entry"] = int(reward["item_entry"])
        result["reward_item_name"] = str(reward.get("item_name") or f"Item {reward['item_entry']}")
    elif kind == "spell" and reward.get("spell_id") not in (None, ""):
        result["reward_spell_id"] = int(reward["spell_id"])
        if reward.get("spell_display_id") not in (None, ""):
            result["reward_spell_display_id"] = int(reward["spell_display_id"])
    return result


def _item_publish_payload_from_release(payload: dict[str, Any], *, record: dict[str, Any], allocator: Any) -> dict[str, Any]:
    item_entry = _int_or_none(payload.get("item_entry"))
    if item_entry is None:
        slot = allocator.peek_next_free_slot(entity_type="item")
        if slot is None:
            raise ValueError("No free managed item slot is available.")
        item_entry = int(slot.reserved_id)
    shape = payload.get("item_shape") if isinstance(payload.get("item_shape"), dict) else {}
    effects = payload.get("effects") if isinstance(payload.get("effects"), list) else []
    spells = []
    for effect in effects:
        if isinstance(effect, dict) and effect.get("spell_id") not in (None, ""):
            spells.append({"spell_id": int(effect["spell_id"]), "trigger": 1})
    return {
        "item_entry": item_entry,
        "base_item_entry": int(payload.get("base_item_entry") or 6948),
        "name": str(payload.get("item_key") or f"WM Autoplay Item {item_entry}")[:120],
        "description": "; ".join(str(note) for note in payload.get("notes", [])[:2]) if isinstance(payload.get("notes"), list) else None,
        "quality": _int_or_none(shape.get("quality")) or 2,
        "required_level": _int_or_none(shape.get("required_level")),
        "clear_stats": True,
        "clear_spells": bool(spells),
        "spells": spells,
        "tags": ["wm_autoplay", "llm_draft"],
        "_wm_reserved_slot": {
            "entity_type": "item",
            "reserved_id": item_entry,
            "arc_key": "wm_autoplay",
            "character_guid": int(payload.get("player_guid") or record.get("player_guid") or 0),
            "notes": [f"draft:{record.get('draft_id')}"],
        },
    }


def _spell_publish_payload_from_release(payload: dict[str, Any], *, record: dict[str, Any], allocator: Any) -> dict[str, Any]:
    spell_entry = _int_or_none(payload.get("spell_entry"))
    if spell_entry is None:
        slot = allocator.peek_next_free_slot(entity_type="spell")
        if slot is None:
            raise ValueError("No free managed spell slot is available.")
        spell_entry = int(slot.reserved_id)
    return {
        "spell_entry": spell_entry,
        "slot_kind": str(payload.get("slot_kind") or "visible_spell_slot"),
        "name": str(payload.get("name") or payload.get("spell_key") or f"WM Autoplay Spell {spell_entry}")[:120],
        "base_visible_spell_id": _int_or_none(payload.get("base_visible_spell_id")) or 133,
        "aura_description": str(payload.get("aura_description") or ""),
        "proc_rules": list(payload.get("proc_rules") or []),
        "linked_spells": list(payload.get("linked_spells") or []),
        "tags": ["wm_autoplay", "llm_draft"],
        "_wm_reserved_slot": {
            "entity_type": "spell",
            "reserved_id": spell_entry,
            "arc_key": "wm_autoplay",
            "character_guid": int(payload.get("player_guid") or record.get("player_guid") or 0),
            "notes": [f"draft:{record.get('draft_id')}"],
        },
    }


def _entry_from_payload(payload: dict[str, Any], lane: str) -> int | None:
    if lane == "quest":
        objective = payload.get("objective") if isinstance(payload.get("objective"), dict) else {}
        return _int_or_none(objective.get("target_entry"))
    if lane == "item":
        return _int_or_none(payload.get("item_entry"))
    if lane == "spell":
        return _int_or_none(payload.get("spell_entry"))
    return None


def _runtime_action_proposal(*, record: dict[str, Any], payload: dict[str, Any]) -> Any:
    from wm.control.models import ControlProposal

    original_source_event = payload.get("source_event") if isinstance(payload.get("source_event"), dict) else None
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    runtime_payload = dict(payload)
    runtime_payload["source_event"] = None
    runtime_payload["idempotency_key"] = str(
        runtime_payload.get("idempotency_key")
        or f"autoplay:action:{record.get('draft_id') or record.get('created_at') or 'draft'}"
    )
    runtime_payload["author"] = {
        "kind": "manual_admin",
        "name": "wm.autoplay",
        "manual_reason": "policy-approved autoplay LLM action draft",
    }
    runtime_payload["metadata"] = {
        **metadata,
        "autoplay_draft_id": record.get("draft_id"),
        "autoplay_lane": record.get("lane"),
        "autoplay_schema_version": record.get("schema_version"),
        "autoplay_source_event": original_source_event,
        "autoplay_original_author": payload.get("author"),
    }
    return ControlProposal.model_validate(runtime_payload)


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


# In-game chat caps. The native bridge clamps each chat packet to 220 chars
# (wm_bridge_environment_actions.cpp ClampChatText), so anything longer must be
# delivered as several messages rather than truncated.
_CHAT_PART_LIMIT = 220
_CHAT_REPLY_MAX_CHARS = 880  # ~4 parts; ceiling so a runaway reply can't flood chat


def _split_chat_message(text: str, *, limit: int = _CHAT_PART_LIMIT) -> list[str]:
    """Split a reply into in-order parts that each fit one chat packet."""
    text = str(text).strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining.strip())
            break
        window = remaining[:limit]
        cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
        if cut >= limit // 2:
            cut += 1  # keep the sentence-ending punctuation with this part
        else:
            cut = window.rfind(" ")
            if cut < limit // 2:
                cut = limit  # no sensible break point; hard split
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return [part for part in parts if part]


def _sanitize_chat_reply(message: str) -> str:
    line = " ".join(str(message).replace("\r", " ").replace("\n", " ").split())
    for token in ("**", "__", "`", "#", "- "):
        line = line.replace(token, "")
    line = line.strip()
    if len(line) >= 2 and line[0] == line[-1] and line[0] in {"'", '"'}:
        line = line[1:-1].strip()
    if len(line) > _CHAT_REPLY_MAX_CHARS:
        line = line[:_CHAT_REPLY_MAX_CHARS - 3].rstrip() + "..."
    return line or "I am listening."


def _guard_chat_reply(message: str) -> str:
    lowered = str(message).lower()
    blocked = (
        "breast",
        "nipple",
        "grope",
        "lick",
        "suck",
        "erotic",
        "fetish",
        "sex",
        "sexual",
    )
    if any(token in lowered for token in blocked):
        return "I will keep this to the world at hand. What do you want to do next?"
    return message


def _fallback_chat_reply(reason: str) -> str:
    del reason
    return "I heard you, but the local model returned no words. Try once more in a moment."


def _chat_context_reset_payload(control_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "epoch": int(control_config.get("llm_chat_context_epoch") or 0),
        "reset_at": control_config.get("llm_chat_context_reset_at"),
        "instruction": "Treat this as the current conversation boundary. Do not rely on any player chat before this reset.",
    }


def _is_forget_context_command(message: str) -> bool:
    normalized = " ".join(str(message).strip().lower().split())
    if normalized.startswith("towm "):
        normalized = normalized.removeprefix("towm ").strip()
    return normalized in {
        "forget context",
        "forget chat context",
        "reset context",
        "reset chat context",
    }


def _forget_context_ack(status: dict[str, Any]) -> str:
    config = status.get("config") if isinstance(status.get("config"), dict) else {}
    epoch = int(config.get("llm_chat_context_epoch") or 0)
    return f"Context forgotten. Fresh WM chat context epoch {epoch} is active."


def _chat_max_tokens(settings: LmStudioSettings) -> int:
    model = str(settings.model or "").lower()
    cap = 512 if "qwen" in model else 128
    return max(64, min(int(settings.max_tokens), cap))


def _chat_identity_facts(context: dict[str, Any], *, player_guid: int) -> dict[str, Any]:
    speaker = context.get("speaker") if isinstance(context.get("speaker"), dict) else {}
    database = context.get("database") if isinstance(context.get("database"), dict) else {}
    character_row = database.get("character_row") if isinstance(database.get("character_row"), dict) else {}
    live = context.get("live_location") if isinstance(context.get("live_location"), dict) else {}
    name = _first_text(speaker.get("name"), character_row.get("name"))
    position = None
    if live.get("x") is not None and live.get("y") is not None:
        position = {"x": live.get("x"), "y": live.get("y"), "z": live.get("z"), "o": live.get("o")}
    location_source = live.get("source") or ("stale_characters_row" if character_row else "unknown")
    return {
        "player_guid": int(player_guid),
        "speaker_name": name,
        "character_name": name,
        "level": _first_text(character_row.get("level")),
        "race": _first_text(character_row.get("race")),
        "class": _first_text(character_row.get("class")),
        "online": _first_text(character_row.get("online")),
        # Live presence wins; the characters-row map/zone are a stale last-saved fallback.
        "map": _first_text(live.get("map_id"), speaker.get("map_id"), character_row.get("map")),
        "zone": _first_text(live.get("zone_id"), speaker.get("zone_id"), character_row.get("zone")),
        "area": _first_text(live.get("area_id"), speaker.get("area_id")),
        "zone_name": _first_text(live.get("zone_name")),
        "area_name": _first_text(live.get("area_name")),
        "position": position,
        "location_source": location_source,
        "location_fresh": bool(live.get("fresh")),
        "remembered": _remembered_facts(context),
    }


def _remembered_facts(context: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    """Compact 'what WM remembers about you' list from persisted steering notes."""
    pack = context.get("session_context_pack") if isinstance(context.get("session_context_pack"), dict) else {}
    notes = pack.get("conversation_steering")
    if not isinstance(notes, list):
        return []
    facts: list[dict[str, Any]] = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        body = _first_text(note.get("body"))
        if not body:
            continue
        if note.get("is_active") is False:
            continue
        facts.append({"kind": _first_text(note.get("steering_kind")) or "player_preference", "body": body})
    return facts[:limit]  # notes arrive priority-ordered from the context pack


# Cheap cues that a message states something durable about the player. Used to
# avoid spending an LLM call on every chat turn just to (almost always) find
# nothing worth remembering. Over-triggering only costs one extra call; the
# schema extractor still makes the real keep/skip decision.
_MEMORY_CUES = (
    "remember", "don't forget", "dont forget", "keep in mind", "note that", "for the record",
    "i prefer", "i like", "i love", "i hate", "i dislike", "i enjoy", "i fear", "afraid of",
    "call me", "my name is", "from now on", "my favorite", "my favourite", "i want you to know",
)


def _looks_like_memory_statement(message: str) -> bool:
    text = str(message).strip().lower()
    if not text:
        return False
    return any(cue in text for cue in _MEMORY_CUES)


# Cheap cues that a message asks WM to stage a multi-step scene (vs. a single
# action). The scene composer still decides whether it is truly a scene; this
# just avoids spending an extra LLM call on ordinary chat.
_SCENE_CUES = (
    "stage", "scene", "summon", "orchestrate", "set up", "set the stage",
    "have it", "have them", "and then", "make a", "perform", "act out", "play out",
    "ambush", "honor guard", "escort", "ritual", "ceremony",
)


def _looks_like_scene_request(message: str) -> bool:
    text = str(message).strip().lower()
    if not text:
        return False
    return any(cue in text for cue in _SCENE_CUES)


def _voice_world_digest(context: dict[str, Any]) -> dict[str, Any]:
    """A tiny world snapshot for the RP voice: location, ambient counts, a little
    recent chat. The heavy sections (full event lists, online roster, quests,
    session pack, verb manifest) are intentionally left out to keep prefill small.
    """
    if not isinstance(context, dict):
        return {}
    live = context.get("live_location") if isinstance(context.get("live_location"), dict) else {}
    perception = context.get("perception") if isinstance(context.get("perception"), dict) else {}
    events = context.get("events") if isinstance(context.get("events"), dict) else {}
    recent_chat = events.get("recent_wm_chat") if isinstance(events.get("recent_wm_chat"), list) else []
    return {
        "live_location": {
            key: live.get(key)
            for key in ("source", "fresh", "zone_id", "area_id", "zone_name", "area_name", "in_combat")
        },
        "perception": {
            "source": perception.get("source"),
            "creature_count": perception.get("creature_count"),
            "gameobject_count": perception.get("gameobject_count"),
        },
        "recent_wm_chat": recent_chat[:3],
    }


def _deterministic_chat_fact_reply(message: str, *, identity: dict[str, Any]) -> str | None:
    lowered = str(message).strip().lower()
    if not lowered:
        return None
    asks_name = (
        "my name" in lowered
        or "character name" in lowered
        or lowered in {"who am i", "who am i?", "what am i called", "what am i called?"}
    )
    if asks_name and identity.get("character_name"):
        return str(identity["character_name"])
    asks_guid = "my guid" in lowered or "player guid" in lowered or "character guid" in lowered
    if asks_guid and identity.get("player_guid") is not None:
        return str(identity["player_guid"])
    return None


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return None


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


def _parse_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _runtime_scene_proposals(*, record: dict[str, Any], payload: dict[str, Any]) -> list[Any]:
    from wm.content.release import compile_scene_release_to_control_scene
    from wm.control.models import ControlProposal
    from wm.control.scene_play import build_scene_proposal
    from wm.control.scene_play import ControlScene
    from wm.control.scene_play import SceneStep

    compiled = compile_scene_release_to_control_scene(payload)
    scene = ControlScene(
        scene_id=str(compiled["id"]),
        description=str(compiled.get("description") or ""),
        steps=[
            SceneStep(
                native_action_kind=str(item["native_action_kind"]),
                payload=dict(item.get("payload") or {}),
                risk_level=str(item.get("risk_level") or "low"),
                delay_seconds=float(item.get("delay_seconds") or 0),
                idempotency_suffix=str(item.get("idempotency_suffix") or index),
                expected_effect=str(item.get("expected_effect") or ""),
            )
            for index, item in enumerate(compiled.get("steps") or [])
            if isinstance(item, dict)
        ],
    )
    if not scene.steps:
        raise ValueError("scene draft compiled without steps")
    player_guid = int(payload.get("player_guid") or record.get("player_guid") or 0)
    if player_guid <= 0:
        raise ValueError("scene draft is missing player_guid")
    run_key = str(record.get("draft_id") or payload.get("scene_key") or "autoplay")
    proposals = []
    for index, step in enumerate(scene.steps):
        proposal = build_scene_proposal(
            scene=scene,
            step=step,
            index=index,
            player_guid=player_guid,
            player_name=None,
            run_key=run_key,
            manual_reason="policy-approved autoplay LLM scene draft",
        )
        proposal_payload = proposal.model_dump(mode="json")
        proposal_payload["metadata"] = {
            **proposal_payload.get("metadata", {}),
            "autoplay_draft_id": record.get("draft_id"),
            "autoplay_lane": record.get("lane"),
            "autoplay_schema_version": record.get("schema_version"),
            "autoplay_source_event": (record.get("opportunity") or {}).get("source_event")
            if isinstance(record.get("opportunity"), dict)
            else None,
        }
        proposals.append(ControlProposal.model_validate(proposal_payload))
    return proposals


def _risk_from_payload(payload: dict[str, Any]) -> str:
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


def _draft_source_event_at(record: dict[str, Any]) -> str | None:
    opportunity = record.get("opportunity") if isinstance(record.get("opportunity"), dict) else {}
    value = opportunity.get("source_event_at") or record.get("source_event_at")
    return str(value) if value else None


def _applied_lane_counts(status: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in status.get("proposal_queue") or []:
        if isinstance(item, dict) and str(item.get("state") or "") == "APPLIED":
            lane = str(item.get("lane") or "")
            if lane:
                counts[lane] = int(counts.get(lane, 0)) + 1
    return counts


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _compact_draft_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in ("draft_id", "lane", "schema_version", "state", "player_guid")
        if key in record
    }


def _compact_request(request: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(request, dict):
        return None
    return {
        "model": request.get("model"),
        "temperature": request.get("temperature"),
        "max_tokens": request.get("max_tokens"),
        "response_format": request.get("response_format"),
    }


def _stable_key(value: str) -> str:
    import hashlib

    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    if "T" not in normalized and " " in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def status_summary(status: dict[str, Any]) -> str:
    readiness = status.get("readiness") or {}
    llm = status.get("llm") or {}
    session = status.get("active_session") or {}
    counters = status.get("counters") or {}
    config = status.get("config") or {}
    return " ".join(
        [
            f"status={status.get('status')}",
            f"running={str(bool(status.get('running'))).lower()}",
            f"paused={str(bool(status.get('paused'))).lower()}",
            f"player_guid={session.get('character_guid') or '(none)'}",
            f"readiness={str(bool(readiness.get('ok'))).lower()}",
            f"llm={str(bool(llm.get('ok'))).lower()}",
            f"model={llm.get('model') or config.get('llm_model') or '(none)'}",
            f"llm_enabled={str(bool(config.get('llm_enabled', True))).lower()}",
            f"wm_chat={str(bool(config.get('llm_chat_enabled', True))).lower()}",
            f"chat_epoch={int(config.get('llm_chat_context_epoch') or 0)}",
            f"lanes={','.join(str(item) for item in config.get('llm_lanes', [])) or '(none)'}",
            f"ticks={counters.get('ticks', 0)}",
            f"drafts={counters.get('drafts_generated', 0)}",
            f"chat={counters.get('chat_replies', 0)}",
            f"issues={len(status.get('issues') or [])}",
            f"maintenance={len(status.get('maintenance_pending') or [])}",
        ]
    )


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _process_exists(pid: int) -> bool:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return str(int(pid)) in (completed.stdout or "")


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


def _compact_chat_world_context(context: dict[str, Any]) -> dict[str, Any]:
    events = context.get("events") if isinstance(context.get("events"), dict) else {}
    database = context.get("database") if isinstance(context.get("database"), dict) else {}
    native = context.get("native_bridge") if isinstance(context.get("native_bridge"), dict) else {}
    session_context = context.get("session_context_pack") if isinstance(context.get("session_context_pack"), dict) else {}
    return {
        "schema_version": context.get("schema_version"),
        "speaker": context.get("speaker"),
        "source_event": context.get("source_event"),
        "online_character_count": len(database.get("online_characters") or []),
        "recent_global_event_count": len(events.get("recent_global") or []),
        "recent_speaker_event_count": len(events.get("recent_for_speaker") or []),
        "recent_wm_chat_count": len(events.get("recent_wm_chat") or []),
        "recent_native_action_count": len(native.get("recent_actions") or []),
        "has_native_context_snapshot": bool(native.get("latest_context_snapshot")),
        "session_context_status": session_context.get("status"),
        "notes": context.get("notes") or [],
    }
